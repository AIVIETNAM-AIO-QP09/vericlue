"""Synthetic statistical oracles; none of these fixtures supports deployment."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.special import rel_entr
from scipy.stats import binom

from vericlue_ml.router.ltt import LTTProtocol, LTTTrial, evaluate_ltt


def protocol(**overrides):
    values = {
        "mode": "voice",
        "grid": [[0.1], [0.5]],
        "expected_attack_types": ["tts", "vc"],
        "alpha": 0.05,
        "delta": 0.025,
        "total_delta": 0.05,
        "family_delta_allocations": {"voice": 0.025, "face": 0.025},
        "sampling_protocol": "Synthetic preselected one utterance per component",
        "target_population": "Synthetic fixture only",
        "independence_attestation": "Independent synthetic observations; no fitted model",
        "one_observation_per_group_per_stratum": True,
        "grid_predeclared": True,
        "independent_of_training_and_calibration": True,
        "objective": "immediate_review_rate",
        "tie_break": "grid_order",
        "fixture_kind": "synthetic",
    }
    values.update(overrides)
    return values


def trials(n=100, *, attack_probability=0.9):
    return [
        {
            "probability": attack_probability,
            "label": "attack",
            "attack_type": kind,
            "group_id": f"{kind}-{i}",
            "partition": "calib_ltt",
        }
        for kind in ("tts", "vc")
        for i in range(n)
    ] + [
        {
            "probability": score,
            "label": "bonafide",
            "group_id": f"b-{i}",
            "partition": "calib_ltt",
        }
        for i, score in enumerate((0.1, 0.3, 0.5, 0.7))
    ]


def hb_oracle(k, n, alpha):
    """Independent binary HB expression, not an import from MAPIE."""
    clipped_risk = min(k / n, alpha)
    divergence = rel_entr(clipped_risk, alpha) + rel_entr(1 - clipped_risk, 1 - alpha)
    return min(float(binom.cdf(k, n, alpha)), math.exp(-n * divergence))


def holm_oracle(p_values, delta):
    rejected = []
    for rank, index in enumerate(sorted(range(len(p_values)), key=p_values.__getitem__)):
        if p_values[index] > delta / (len(p_values) - rank):
            break
        rejected.append(index)
    return sorted(rejected)


def test_voice_inclusive_boundary_and_predeclared_objective_selects_less_review():
    report = evaluate_ltt(protocol(), trials())
    assert report["selected"]["parameters"] == [0.5]
    assert report["candidates"][0]["bonafide_counts"] == {
        "pass": 1,
        "review": 3,
        "voice_challenge": 0,
        "n": 4,
    }
    assert report["selected"]["immediate_review_rate"] == 0.25
    assert report["diagnostic_only"] is True
    assert report["runtime_eligible"] is False
    assert report["provisional"] is True
    assert report["external_attestation_verified"] is False
    assert report["fixture_kind"] == "synthetic"


@pytest.mark.parametrize(
    "k,n,alpha", [(0, 100, 0.05), (4, 100, 0.1), (20, 100, 0.1), (100, 100, 0.1)]
)
def test_per_stratum_raw_p_values_match_independent_binary_hb(k, n, alpha):
    rows = trials(n)
    for row in rows[:k]:
        row["probability"] = 0.1
    result = evaluate_ltt(protocol(alpha=alpha), rows)
    candidate = result["candidates"][0]
    assert candidate["risks"]["tts"]["p_value"] == pytest.approx(hb_oracle(k, n, alpha), rel=1e-12)
    assert candidate["risks"]["tts"]["n"] == n
    assert candidate["risks"]["tts"]["failures"] == k


def test_worst_stratum_blocks_safe_pooled_average():
    rows = trials(1000)
    for row in rows[1000:]:
        if row["label"] == "attack":
            row["probability"] = 0.1
    result = evaluate_ltt(protocol(), rows)
    assert result["selected"] is None
    assert all(c["combined_p_value"] == 1 for c in result["candidates"])


def test_holm_applies_to_entire_declared_grid_with_inclusive_boundary():
    # A dyadic probability makes the equality exact, without numerical drift
    # between independent evaluations of logarithms and the binomial CDF.
    p = hb_oracle(0, 4, 0.5)
    boundary_delta = 2 * p
    pconfig = protocol(
        alpha=0.5,
        delta=boundary_delta,
        total_delta=0.2,
        family_delta_allocations={"voice": boundary_delta, "face": 0.01},
    )
    result = evaluate_ltt(pconfig, trials(4))
    ps = [c["combined_p_value"] for c in result["candidates"]]
    assert (
        [c["index"] for c in result["candidates"] if c["statistically_valid"]]
        == holm_oracle(ps, boundary_delta)
        == [0, 1]
    )
    lower = boundary_delta * (1 - 1e-10)
    pconfig.update(delta=lower, family_delta_allocations={"voice": lower, "face": 0.01})
    assert evaluate_ltt(pconfig, trials(4))["selected"] is None


def test_face_counts_pass_review_challenge_separately_and_ties_use_grid_order():
    result = evaluate_ltt(protocol(mode="face", grid=[[0.2, 0.7], [0.3, 0.7]]), trials())
    assert result["selected"]["index"] == 0
    assert result["selected"]["bonafide_counts"] == {
        "pass": 1,
        "review": 1,
        "voice_challenge": 2,
        "n": 4,
    }
    assert result["selected"]["immediate_review_rate"] == 0.25


def test_optional_bpcer_is_another_max_p_risk_and_can_block_selection():
    result = evaluate_ltt(protocol(bpcer_alpha=0.05), trials())
    assert result["selected"] is None
    assert result["candidates"][0]["risks"]["bonafide_bpcer"]["failures"] == 3


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -0.1, 1.1, True, "0.1"])
def test_invalid_probability_never_disappears(value):
    rows = trials()
    rows[0]["probability"] = value
    with pytest.raises(ValueError):
        evaluate_ltt(protocol(), rows)


@pytest.mark.parametrize(
    "changes",
    [
        {"partition": "test"},
        {"partition": "calib_fit"},
        {"group_id": " "},
        {"status": "error"},
        {"status": "degraded"},
        {"label": 1},
        {"attack_type": "unknown"},
        {"attack_type": None},
    ],
)
def test_unusable_trial_blocks_entire_evaluation(changes):
    rows = trials()
    rows[0].update(changes)
    with pytest.raises(ValueError):
        evaluate_ltt(protocol(), rows)


def test_duplicate_dependence_component_in_stratum_rejected_without_deduplication():
    rows = trials()
    rows[1]["group_id"] = rows[0]["group_id"]
    with pytest.raises(ValueError, match="group"):
        evaluate_ltt(protocol(), rows)


def test_missing_stratum_and_missing_bonafide_block_selection():
    with pytest.raises(ValueError, match="strat"):
        evaluate_ltt(protocol(), [r for r in trials() if r.get("attack_type") != "vc"])
    with pytest.raises(ValueError, match="bonafide"):
        evaluate_ltt(protocol(), [r for r in trials() if r["label"] == "attack"])


@pytest.mark.parametrize(
    "changes",
    [
        {"grid": []},
        {"grid": [[0.1], [0.1]]},
        {"grid": [[0.5, 0.3]]},
        {"grid": [[True]]},
        {"grid": [[float("nan")]]},
        {"alpha": 0.0},
        {"alpha": True},
        {"delta": "0.025"},
        {"expected_attack_types": []},
        {"expected_attack_types": ["tts", "tts"]},
        {"sampling_protocol": " "},
        {"independence_attestation": ""},
        {"target_population": ""},
        {"one_observation_per_group_per_stratum": False},
        {"grid_predeclared": False},
        {"independent_of_training_and_calibration": False},
        {"grid_predeclared": 1},
        {"family_delta_allocations": {"voice": 0.05, "face": 0.05}},
        {"family_delta_allocations": {"voice": 0.01, "face": 0.025}},
        {"objective": "pass_rate"},
        {"tie_break": "posthoc"},
    ],
)
def test_invalid_or_unattested_protocol_fails_closed(changes):
    with pytest.raises(ValueError):
        evaluate_ltt(protocol(**changes), trials())


def test_typed_and_json_inputs_preserve_grid_and_remain_diagnostic():
    import json

    parsed = LTTProtocol.model_validate_json(json.dumps(protocol(fixture_kind="research")))
    typed_rows = [LTTTrial.model_validate(row) for row in trials()]
    report = evaluate_ltt(parsed, typed_rows)
    assert report["protocol"]["grid"] == [[0.1], [0.5]]
    assert report["selected"] is not None
    assert report["runtime_eligible"] is False
    assert np.isfinite([c["combined_p_value"] for c in report["candidates"]]).all()
