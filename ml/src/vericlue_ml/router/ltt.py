"""Offline, conditional LTT diagnostics; never a source of runtime thresholds.

MAPIE 1.4.1 ``BinaryClassificationController`` supplies binary Hoeffding--Bentkus
p-values, one controller per attack stratum (and optional bonafide review risk).
Their maximum is the intersection-union p-value for each declared candidate.
Only then does MAPIE's public Holm procedure test the entire declared grid.
Source/API: scikit-learn-contrib/MAPIE tag v1.4.1,
mapie/risk_control/{binary_classification,methods,fwer_control}.py (BSD-3-Clause).
No statistical formula from that project is copied here.

The caller must establish independent sampling, frozen upstream models and a
predeclared protocol. Declarations here are self-reported, not independently
verified evidence. Synthetic success cannot establish deployment readiness.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from importlib.metadata import version
from typing import Annotated, Any, Literal

import numpy as np
from mapie.risk_control import BinaryClassificationController
from mapie.risk_control.fwer_control import FWERBonferroniHolm, FWERProcedure
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, model_validator

Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
RiskLevel = Annotated[float, Field(strict=True, gt=0, lt=1, allow_inf_nan=False)]
Text = Annotated[StrictStr, Field(min_length=1)]


class LTTProtocol(BaseModel):
    """Self-declared sampling and error budgets, frozen before calib_ltt scores.

    ``grid`` contains ``(threshold,)`` for voice or ``(B, A)`` for face.
    The objective minimizes immediate review among bonafide observations, with
    ties resolved by the declared grid order. Optional ``bpcer_alpha`` controls
    that same bonafide immediate rejection event; challenge is counted separately.
    Family allocations explicitly split the total face/voice failure budget.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    mode: Literal["voice", "face"]
    grid: tuple[tuple[Probability, ...], ...]
    expected_attack_types: tuple[Text, ...]
    alpha: RiskLevel
    delta: RiskLevel
    total_delta: RiskLevel
    family_delta_allocations: dict[Literal["voice", "face"], RiskLevel]
    sampling_protocol: Text
    target_population: Text
    independence_attestation: Text
    one_observation_per_group_per_stratum: StrictBool
    grid_predeclared: StrictBool
    independent_of_training_and_calibration: StrictBool
    objective: Literal["immediate_review_rate"]
    tie_break: Literal["grid_order"]
    fixture_kind: Literal["synthetic", "research"]
    bpcer_alpha: RiskLevel | None = None

    @model_validator(mode="after")
    def valid_protocol(self) -> LTTProtocol:
        if not self.grid or len(set(self.grid)) != len(self.grid):
            raise ValueError("A nonempty unique predeclared grid is required")
        width = 1 if self.mode == "voice" else 2
        for parameters in self.grid:
            if len(parameters) != width or (width == 2 and parameters[0] >= parameters[1]):
                raise ValueError("Grid must contain voice (t,) or face (B,A) with B < A")
        if not self.expected_attack_types or len(set(self.expected_attack_types)) != len(
            self.expected_attack_types
        ):
            raise ValueError("Unique nonempty expected attack strata are required")
        if "bonafide_bpcer" in self.expected_attack_types:
            raise ValueError("bonafide_bpcer is reserved for the bonafide risk")
        for value in (
            *self.expected_attack_types,
            self.sampling_protocol,
            self.target_population,
            self.independence_attestation,
        ):
            if not value.strip():
                raise ValueError("Protocol descriptions and strata cannot be blank")
        if not all(
            (
                self.one_observation_per_group_per_stratum,
                self.grid_predeclared,
                self.independent_of_training_and_calibration,
            )
        ):
            raise ValueError("Predeclaration and independence attestations are required")
        allocations = self.family_delta_allocations
        if set(allocations) != {"face", "voice"}:
            raise ValueError("Declare both face and voice delta allocations")
        if sum(allocations.values()) > self.total_delta + 1e-15:
            raise ValueError("Family delta allocations exceed total delta")
        if not math.isclose(allocations[self.mode], self.delta, rel_tol=0, abs_tol=1e-15):
            raise ValueError("delta must equal the selected family's allocation")
        return self


class LTTTrial(BaseModel):
    """A diagnostic candidate probability, deliberately distinct from ModuleResult.

    There is no status upgrade path. Failed/missing scores must stop the caller;
    they cannot be represented as an accepted trial or silently dropped here.
    ``group_id`` identifies the full connected person/source dependence component.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    probability: Probability
    label: Literal["attack", "bonafide"]
    attack_type: Text | None = None
    group_id: Text
    partition: Literal["calib_ltt"]

    @model_validator(mode="after")
    def valid_trial(self) -> LTTTrial:
        if not self.group_id.strip():
            raise ValueError("A nonblank dependence group is required")
        if self.label == "attack" and (self.attack_type is None or not self.attack_type.strip()):
            raise ValueError("Attack trials require an attack stratum")
        if self.label == "bonafide" and self.attack_type is not None:
            raise ValueError("Bonafide trials cannot carry an attack stratum")
        return self


class _CollectRawPValues(FWERProcedure):
    """Public MAPIE extension hook that makes no local rejection decisions.

    Controller.calibrate still computes p_values, but no stratum independently
    selects a threshold. Final rejection is exclusively global Holm below.
    """

    def _init_state(self, n_lambdas: int, delta: float) -> None:
        self.n_lambdas = n_lambdas

    def _select_next_hypothesis(self, p_values: np.ndarray) -> None:
        return None

    def _local_significance_levels(self) -> np.ndarray:
        return np.zeros(self.n_lambdas)

    def _update_on_reject(self, hypothesis_index: int) -> None:
        raise RuntimeError("Raw p-value collection never rejects a hypothesis")


def _raw_p_values(
    probabilities: np.ndarray, protocol: LTTProtocol, *, bonafide: bool
) -> np.ndarray:
    def predict_event(scores: np.ndarray, *parameters: float) -> np.ndarray:
        if bonafide:
            # Voice is inclusive-pass; face is inclusive-review at A.
            return (
                scores > parameters[0] if protocol.mode == "voice" else scores >= parameters[1]
            ).astype(int)
        return (scores <= parameters[0]).astype(int)

    controller = BinaryClassificationController(
        predict_function=predict_event,
        risk="predicted_positive_fraction",
        best_predict_param_choice="predicted_positive_fraction",
        target_level=protocol.bpcer_alpha if bonafide else protocol.alpha,
        confidence_level=1 - protocol.delta,
        list_predict_params=np.asarray(protocol.grid),
        fwer_method=_CollectRawPValues(),
    )
    # The collector intentionally produces no local valid parameters. Suppress
    # only that expected selection warning, without hiding statistical warnings.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="No predict parameters were found to control the risk.*"
        )
        controller.calibrate(probabilities, np.zeros(len(probabilities), dtype=int))
    p_values = np.asarray(controller.p_values, dtype=float).reshape(-1)
    if (
        p_values.shape != (len(protocol.grid),)
        or not np.isfinite(p_values).all()
        or ((p_values < 0) | (p_values > 1)).any()
    ):
        raise ValueError("MAPIE returned invalid raw p-values")
    return p_values


def _decision_counts(
    rows: Sequence[LTTTrial], mode: str, parameters: tuple[float, ...]
) -> dict[str, int]:
    counts = {"pass": 0, "review": 0, "voice_challenge": 0, "n": len(rows)}
    for row in rows:
        if row.probability <= parameters[0]:
            decision = "pass"
        elif mode == "voice" or row.probability >= parameters[1]:
            decision = "review"
        else:
            decision = "voice_challenge"
        counts[decision] += 1
    return counts


def evaluate_ltt(
    protocol: LTTProtocol | Mapping[str, Any],
    trials: Sequence[LTTTrial | Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate every declared candidate, returning selected=null if none qualify.

    Invalid inputs raise ValueError rather than changing the grid, dropping rows,
    or weakening the declared conditions. Results are always provisional offline
    diagnostics, including when all conditional statistical tests reject.
    """
    if version("mapie") != "1.4.1":
        raise ValueError("This offline adapter requires exactly mapie==1.4.1")
    # Revalidate even existing model instances (including mutable nested fields).
    declared = LTTProtocol.model_validate(
        protocol.model_dump() if isinstance(protocol, LTTProtocol) else dict(protocol)
    )
    rows = [
        LTTTrial.model_validate(row.model_dump() if isinstance(row, LTTTrial) else dict(row))
        for row in trials
    ]
    strata: dict[str, list[LTTTrial]] = {kind: [] for kind in declared.expected_attack_types}
    bonafide_rows = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        stratum = row.attack_type if row.label == "attack" else "bonafide_bpcer"
        if row.label == "attack" and stratum not in strata:
            raise ValueError(f"Unexpected attack stratum: {stratum}")
        identity = (str(stratum), row.group_id)
        if identity in seen:
            raise ValueError(f"Repeated dependence group within stratum: {identity}")
        seen.add(identity)
        if row.label == "attack":
            strata[str(stratum)].append(row)
        else:
            bonafide_rows.append(row)
    if any(not entries for entries in strata.values()):
        raise ValueError("Missing expected attack stratum")
    if not bonafide_rows:
        raise ValueError("The predeclared review objective requires bonafide observations")

    risk_rows = dict(strata)
    if declared.bpcer_alpha is not None:
        risk_rows["bonafide_bpcer"] = bonafide_rows
    raw = {
        kind: _raw_p_values(
            np.asarray([row.probability for row in entries]),
            declared,
            bonafide=kind == "bonafide_bpcer",
        )
        for kind, entries in risk_rows.items()
    }
    combined = np.max(np.stack(list(raw.values())), axis=0)
    valid_indices = set(FWERBonferroniHolm().run(combined, declared.delta).tolist())
    candidates = []
    for index, parameters in enumerate(declared.grid):
        bonafide_counts = _decision_counts(bonafide_rows, declared.mode, parameters)
        risks = {}
        for kind, entries in risk_rows.items():
            counts = _decision_counts(entries, declared.mode, parameters)
            failures = counts["review"] if kind == "bonafide_bpcer" else counts["pass"]
            risks[kind] = {
                "n": len(entries),
                "failures": failures,
                "empirical_risk": failures / len(entries),
                "p_value": float(raw[kind][index]),
                "target": declared.bpcer_alpha if kind == "bonafide_bpcer" else declared.alpha,
                "decision_counts": counts,
            }
        candidates.append(
            {
                "index": index,
                "parameters": list(parameters),
                "risks": risks,
                "combined_p_value": float(combined[index]),
                "statistically_valid": index in valid_indices,
                "bonafide_counts": bonafide_counts,
                "immediate_review_rate": bonafide_counts["review"] / len(bonafide_rows),
            }
        )
    valid = [candidate for candidate in candidates if candidate["statistically_valid"]]
    selected = min(valid, key=lambda c: (c["immediate_review_rate"], c["index"])) if valid else None
    return {
        "diagnostic_only": True,
        "runtime_eligible": False,
        "provisional": True,
        "external_attestation_verified": False,
        "fixture_kind": declared.fixture_kind,
        "protocol": declared.model_dump(mode="json"),
        "method": "MAPIE-1.4.1/binary-Hoeffding-Bentkus/max-p/global-Holm",
        "objective_scope": "bonafide_immediate_review; face challenge is counted separately",
        "sample_count": len(rows),
        "candidates": candidates,
        "selected": selected,
    }
