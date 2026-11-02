"""Offline NES2Net candidate diagnostics with frozen calibration and locked LTT.

Declarations describe measured runtimes and sampling; they are self-reported,
not external attestations. No artifact produced here is eligible for deployment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from vericlue_ml.common.calibration import Calibrator
from vericlue_ml.eval import metrics
from vericlue_ml.eval import nes2net_utterance as utterance
from vericlue_ml.router.ltt import LTTProtocol, LTTTrial, evaluate_ltt


class MeasuredRuntime(BaseModel):
    """Typed identity of the measurement host, independent of this scorer host."""

    model_config = ConfigDict(extra="forbid", strict=True)
    system: Literal["Windows", "Linux"]
    python: str = Field(min_length=1)
    torch: str = Field(min_length=1)
    transformers: str = Field(min_length=1)
    numpy: str = Field(min_length=1)
    cpu_threads: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def nonblank_versions(self):
        if any(
            not getattr(self, key).strip() for key in ("python", "torch", "transformers", "numpy")
        ):
            raise ValueError("Measured runtime versions must be nonblank")
        return self


class FitEnvelope(BaseModel):
    """Exact envelope emitted by utterance.fit_report, without identity fallback."""

    model_config = ConfigDict(extra="forbid", strict=True)
    artifact: dict
    measurement_report_sha256: str = Field(pattern=utterance.HASH)
    measurement_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    fitting_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    protocol: Literal[utterance.PROTOCOL]
    excluded_calib_fit: dict[str, StrictInt]
    deployed: Literal[False]


def _binding(header) -> dict:
    return {
        "model_version": header.model_version,
        "checkpoint_sha256": header.checkpoint_sha256,
        "parity_report_sha256": header.parity_report_sha256,
        "numerical_binding": header.numerical_binding,
        "runtime": MeasuredRuntime.model_validate(header.runtime).model_dump(),
        "protocol": header.protocol,
    }


class _Inputs:
    """Bounded snapshots, full-union groups and a single validated fit envelope."""

    def __init__(self, report: Path, fit_report: Path, fit_measurement: Path, *extra: Path):
        self.hashes: dict[Path, str] = {}
        self.measurements: dict[Path, tuple] = {}
        for path in (report, fit_measurement, *extra):
            path = Path(path).resolve()
            if path not in self.measurements:
                value = utterance._validated_measurement(path)
                self.measurements[path] = value
                self.hashes[path] = value[1]
        self.report = self.measurements[Path(report).resolve()]
        self.fit_measurement = self.measurements[Path(fit_measurement).resolve()]
        self.binding = _binding(self.report[0])
        samples, checks, seen = [], [], set()
        for header, digest, rows in self.measurements.values():
            if _binding(header) != self.binding or header.dataset != self.report[0].dataset:
                raise ValueError("Measurement model/parity/runtime/dataset binding differs")
            if digest in seen:
                continue
            seen.add(digest)
            for sample, row, _ in rows:
                samples.append(sample)
                checks.append(row)
        # Includes failed and unused rows and secondary identities. Never recompute
        # components on a selected/complete-case subset.
        self.groups = utterance._partition(samples, checks)
        body, checksum = self.snapshot(fit_report)
        envelope = FitEnvelope.model_validate(body)
        if body.get("deployed") is not False:
            raise ValueError("Fit envelope must explicitly declare deployed=false")
        raw = envelope.artifact
        if (
            raw.get("provisional") is not False
            or type(raw.get("n_pos")) is not int
            or type(raw.get("n_neg")) is not int
        ):
            raise ValueError("A nonprovisional fitted calibrator with integer counts is required")
        self.calibrator = Calibrator.model_validate_json(json.dumps(raw), strict=True)
        fit_header, fit_hash, fit_rows = self.fit_measurement
        counts = Counter()
        excluded = Counter()
        for sample, _, result in fit_rows:
            if sample.split == "calib_fit":
                if result.score is None:
                    excluded[str(result.status)] += 1
                else:
                    counts[sample.label] += 1
        if (
            envelope.measurement_report_sha256 != fit_hash
            or envelope.measurement_commit != fit_header.source_commit
            or envelope.fitting_commit != self.calibrator.commit
            or self.calibrator.module != "voice_spoof"
            or self.calibrator.model_version != fit_header.model_version
            or self.calibrator.dataset != fit_header.dataset
            or self.calibrator.n_pos != counts[1]
            or self.calibrator.n_neg != counts[0]
            or envelope.excluded_calib_fit != dict(excluded)
        ):
            raise ValueError("Fit envelope does not match linked measurement provenance/counts")
        self.fit_hash = checksum
        self.envelope = envelope

    def snapshot(self, path: Path) -> tuple[dict, str]:
        path = Path(path).resolve()
        body, digest = utterance._snapshot(path)
        if path in self.hashes and self.hashes[path] != digest:
            raise ValueError("Input changed during candidate processing")
        self.hashes[path] = digest
        return body, digest

    def scored(self, measurement: tuple, split: str) -> list[dict]:
        selected = [(s, r, a) for s, r, a in measurement[2] if s.split == split]
        if not selected or any(result.score is None for _, _, result in selected):
            raise ValueError("Target split must contain complete parity-bound measurements")
        probabilities = self.calibrator.predict([result.score for _, _, result in selected])
        return [
            {
                "sample": sample.model_dump(),
                "group_id": self.groups[sample.sample_id],
                "candidate_probability": float(probability),
                "module_result": result.to_contract(),
            }
            for (sample, _, result), probability in zip(selected, probabilities, strict=True)
        ]

    def base(self, measurement: tuple, rows: list[dict], split: str) -> dict:
        header, digest, _ = measurement
        return {
            "schema_version": 1,
            "diagnostic_only": True,
            "deployed": False,
            "runtime_eligible": False,
            "external_attestation_verified": False,
            "dataset": header.dataset,
            "model_version": header.model_version,
            "measurement_commit": header.source_commit,
            "fitting_commit": self.envelope.fitting_commit,
            "fit_measurement_commit": self.fit_measurement[0].source_commit,
            "measurement_report_sha256": digest,
            "fit_report_sha256": self.fit_hash,
            "fit_measurement_sha256": self.fit_measurement[1],
            "binding": self.binding,
            "split": split,
            "sample_count": len(rows),
            "class_counts": dict(
                Counter("attack" if r["sample"]["label"] else "bonafide" for r in rows)
            ),
            "attack_type_counts": dict(
                Counter(r["sample"]["attack_type"] for r in rows if r["sample"]["label"])
            ),
            "excluded_calib_fit": self.envelope.excluded_calib_fit,
            "rows": rows,
        }

    def write(self, output: Path, payload: dict) -> None:
        target = Path(output).resolve()
        repo = Path(__file__).resolve().parents[4]
        forbidden = [
            repo / p for p in ("ml/configs", "models", "data", "external", "packages/contracts")
        ]
        forbidden += [
            Path(os.environ[key]).resolve()
            for key in ("MODELS_DIR", "DATA_DIR", "CALIBRATORS_DIR")
            if os.environ.get(key)
        ]
        if any(target.is_relative_to(path.resolve()) for path in forbidden):
            raise ValueError("Output must be outside config/model/data storage")
        for path, digest in self.hashes.items():
            if utterance._snapshot(path)[1] != digest:
                raise ValueError("Input changed during candidate processing")
        utterance._write(Path(output), payload, protected=list(self.hashes))


def score_report(
    report: Path,
    fit_report: Path,
    fit_measurement: Path,
    output: Path,
    *,
    split: Literal["calib_fit", "calib_ltt"],
) -> dict:
    """Apply a linked frozen calibrator; test scoring requires locked evaluation."""
    if split not in ("calib_fit", "calib_ltt"):
        raise ValueError("Direct scoring of test is forbidden before locked selection")
    commit = _execution_commit()
    inputs = _Inputs(report, fit_report, fit_measurement)
    rows = inputs.scored(inputs.report, split)
    payload = inputs.base(inputs.report, rows, split)
    payload["scoring_commit"] = commit
    inputs.write(output, payload)
    return payload


def _execution_commit() -> str:
    commit = utterance.git_revision()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("Commit candidate implementation before producing artifacts")
    return commit


def _selection(inputs: _Inputs, measurement: tuple, protocol_path: Path) -> dict:
    body, protocol_hash = inputs.snapshot(protocol_path)
    protocol = LTTProtocol.model_validate(body)
    if protocol.mode != "voice":
        raise ValueError("NES2Net candidate selection requires a voice protocol")
    rows = inputs.scored(measurement, "calib_ltt")
    trials = [
        LTTTrial(
            probability=row["candidate_probability"],
            label="attack" if row["sample"]["label"] else "bonafide",
            attack_type=row["sample"]["attack_type"] if row["sample"]["label"] else None,
            group_id=row["group_id"],
            partition="calib_ltt",
        )
        for row in rows
    ]
    outcome = evaluate_ltt(protocol, trials)
    return {
        **inputs.base(measurement, rows, "calib_ltt"),
        "artifact_kind": "nes2net_voice_ltt",
        "protocol_path": str(Path(protocol_path).resolve()),
        "protocol_sha256": protocol_hash,
        "locked_protocol": protocol.model_dump(mode="json"),
        "fixture_kind": protocol.fixture_kind,
        "ltt_outcome": outcome,
        "selected": outcome["selected"],
    }


def select_report(
    report: Path, fit_report: Path, fit_measurement: Path, protocol_path: Path, output: Path
) -> dict:
    """Select only from complete calib_ltt observations and the predeclared grid."""
    commit = _execution_commit()
    inputs = _Inputs(report, fit_report, fit_measurement)
    payload = _selection(inputs, inputs.report, protocol_path)
    payload["selection_commit"] = commit
    inputs.write(output, payload)
    return payload


def _test_metrics(rows: list[dict], threshold: float) -> dict:
    labels = [row["sample"]["label"] for row in rows]
    probabilities = [row["candidate_probability"] for row in rows]
    kinds = sorted({row["sample"]["attack_type"] for row in rows if row["sample"]["label"]})
    # Core LTT uses inclusive acceptance p <= t; existing descriptive metrics'
    # APCER/BPCER helpers use p < t, so fixed-threshold counts are explicit here.
    by_type = {}
    for kind in kinds:
        attack = [r for r in rows if r["sample"]["label"] and r["sample"]["attack_type"] == kind]
        accepted = sum(r["candidate_probability"] <= threshold for r in attack)
        by_type[kind] = {"n": len(attack), "accepted": accepted, "apcer": accepted / len(attack)}
    bonafide = [r for r in rows if not r["sample"]["label"]]
    rejected = sum(r["candidate_probability"] > threshold for r in bonafide)
    apcers = {kind: value["apcer"] for kind, value in by_type.items()}
    return {
        "auc": metrics.auc(labels, probabilities),
        "eer": metrics.eer(labels, probabilities),
        "ece": metrics.ece(labels, probabilities),
        "brier": metrics.brier_score(labels, probabilities),
        "apcer_by_attack": apcers,
        "attack_counts": by_type,
        "max_apcer": max(apcers.values()) if apcers else None,
        "max_apcer_scope": "observed_attack_types_only",
        "bpcer": rejected / len(bonafide) if bonafide else None,
        "bonafide_n": len(bonafide),
        "bonafide_rejected": rejected,
        "acceptance_rule": "candidate_probability <= locked_threshold",
        "uncertainty": "Descriptive only; no per-clip iid confidence interval is asserted",
    }


def evaluate_candidate(
    report: Path,
    fit_report: Path,
    fit_measurement: Path,
    ltt_report: Path,
    ltt_measurement: Path,
    output: Path,
) -> dict:
    """Evaluate test only after replaying and verifying the complete locked LTT artifact."""
    commit = _execution_commit()
    inputs = _Inputs(report, fit_report, fit_measurement, ltt_measurement)
    locked, lock_hash = inputs.snapshot(ltt_report)
    if not isinstance(locked, dict) or not isinstance(locked.get("protocol_path"), str):
        raise ValueError("A valid locked LTT artifact and protocol reference are required")
    selection_commit = locked.get("selection_commit")
    if (
        not isinstance(selection_commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", selection_commit) is None
    ):
        raise ValueError("Locked artifact requires its original selection commit")
    ltt = inputs.measurements[Path(ltt_measurement).resolve()]
    recomputed = _selection(inputs, ltt, Path(locked["protocol_path"]))
    recomputed["selection_commit"] = selection_commit
    if recomputed != locked or recomputed["selected"] is None:
        raise ValueError(
            "Locked LTT artifact differs from recomputation or has no selected candidate"
        )
    # No test probabilities or descriptive threshold sweeps precede this gate.
    rows = inputs.scored(inputs.report, "test")
    threshold = recomputed["selected"]["parameters"][0]
    expected = recomputed["locked_protocol"]["expected_attack_types"]
    observed = {row["sample"]["attack_type"] for row in rows if row["sample"]["label"]}
    missing = [kind for kind in expected if kind not in observed]
    unexpected = sorted(observed - set(expected))
    classes = {
        "bonafide": any(not row["sample"]["label"] for row in rows),
        "attack": any(row["sample"]["label"] for row in rows),
    }
    payload = {
        **inputs.base(inputs.report, rows, "test"),
        "fixture_kind": recomputed["fixture_kind"],
        "evaluation_commit": commit,
        "selection_commit": selection_commit,
        "ltt_report_sha256": lock_hash,
        "ltt_measurement_sha256": ltt[1],
        "ltt_measurement_commit": ltt[0].source_commit,
        "protocol_sha256": recomputed["protocol_sha256"],
        "locked_protocol": recomputed["locked_protocol"],
        "threshold": threshold,
        "expected_attack_types": expected,
        "missing_expected_attack_types": missing,
        "unexpected_attack_types": unexpected,
        "class_coverage": classes,
        "evaluation_complete": all(classes.values()) and not missing and not unexpected,
        "metrics": _test_metrics(rows, threshold),
    }
    inputs.write(output, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run local, explicit score/select/evaluate commands without deployment writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("score", "select", "evaluate"):
        cmd = sub.add_parser(name)
        for key in ("report", "fit-report", "fit-measurement", "output"):
            cmd.add_argument("--" + key, required=True, type=Path)
        if name == "score":
            cmd.add_argument("--split", required=True, choices=("calib_fit", "calib_ltt"))
        elif name == "select":
            cmd.add_argument("--protocol", required=True, type=Path)
        else:
            cmd.add_argument("--ltt-report", required=True, type=Path)
            cmd.add_argument("--ltt-measurement", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "score":
        score_report(
            args.report, args.fit_report, args.fit_measurement, args.output, split=args.split
        )
    elif args.command == "select":
        select_report(
            args.report, args.fit_report, args.fit_measurement, args.protocol, args.output
        )
    else:
        evaluate_candidate(
            args.report,
            args.fit_report,
            args.fit_measurement,
            args.ltt_report,
            args.ltt_measurement,
            args.output,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
