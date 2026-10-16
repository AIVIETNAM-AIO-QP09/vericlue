"""ROUT-02 policy acceptance using deterministic mock ModuleResults on CPU."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, Status
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.router.config import load_config
from vericlue_ml.router.policy import TrustRouter


@pytest.fixture
def router():
    return TrustRouter()


def results(scenario="genuine"):
    inp = DetectorInput(metadata={"scenario": scenario})
    return {module: MockDetector(module).predict(inp) for module in Module}


def replace_result(values, module, **updates):
    values[module] = values[module].model_copy(update=updates, deep=True)
    return values


@pytest.mark.parametrize(
    "scenario,status,priority",
    [
        ("genuine", "pass", "normal"),
        ("print", "review", "high"),
        ("replay", "review", "high"),
        ("virtual_cam", "review", "high"),
        ("faceswap", "review", "high"),
        ("voice_clone", "voice_challenge", "normal"),
        ("low_quality", "retry", "normal"),
    ],
)
def test_seven_mock_scenarios_have_stable_finalize_decisions(router, scenario, status, priority):
    decision = router.finalize(results(scenario))
    assert decision.status == status
    assert decision.priority == priority
    assert decision.config_version.startswith("sha256:")
    assert len(decision.config_version) == 71
    assert isinstance(decision.thresholds, dict) and decision.thresholds


def test_voice_clone_after_face_challenge_goes_to_review(router):
    values = results("voice_clone")
    assert router.finalize(values).status == "voice_challenge"
    assert router.voice(values).status == "review"


@pytest.mark.parametrize("retries,expected", [(0, "retry"), (1, "retry"), (2, "review")])
def test_quality_failure_precedes_degraded_face_and_exhausts_retry_limit(router, retries, expected):
    values = results("low_quality")
    assert values[Module.FACE_PAD].status == Status.DEGRADED
    assert values[Module.FACE_DEEPFAKE].status == Status.DEGRADED
    decision = router.finalize(values, retries_used=retries)
    assert decision.status == expected
    if expected == "retry":
        assert decision.retry_hint == "MORE_LIGHT"


@pytest.mark.parametrize("status", [Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE])
def test_quality_status_failure_never_becomes_retry_or_pass(router, status):
    values = replace_result(results("low_quality"), Module.QUALITY, status=status)
    assert router.finalize(values).status == "review"


@pytest.mark.parametrize("module", [Module.FACE_PAD, Module.FACE_DEEPFAKE])
@pytest.mark.parametrize("status", [Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE])
def test_quality_pass_and_unusable_face_module_requires_review(router, module, status):
    values = replace_result(results(), module, status=status, prob_attack=0)
    assert router.finalize(values).status == "review"


@pytest.mark.parametrize(
    "module",
    [Module.QUALITY, Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.CHROMAPULSE, Module.CAMPROBE],
)
def test_missing_required_finalize_module_requires_review(router, module):
    values = results()
    del values[module]
    assert router.finalize(values).status == "review"


@pytest.mark.parametrize("module", [Module.FACE_PAD, Module.FACE_DEEPFAKE])
def test_missing_probability_of_one_face_module_cannot_use_other_or_raw_score(router, module):
    values = replace_result(results(), module, prob_attack=None, score=0)
    assert router.finalize(values).status == "review"


@pytest.mark.parametrize(
    "probability,status",
    [
        (0.15, "pass"),
        (0.150001, "voice_challenge"),
        (0.599999, "voice_challenge"),
        (0.60, "review"),
    ],
)
def test_face_threshold_boundaries_are_inclusive_at_pass_and_review(router, probability, status):
    values = results()
    for module in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
        replace_result(values, module, prob_attack=probability)
    assert router.finalize(values).status == status


@pytest.mark.parametrize("module", [Module.CHROMAPULSE, Module.CAMPROBE])
def test_presence_fail_is_high_priority_and_unclear_retries(router, module):
    values = replace_result(results(), module, gate=Gate.FAIL)
    decision = router.finalize(values)
    assert decision.status == "review" and decision.priority == "high"
    replace_result(values, module, gate=Gate.UNCLEAR)
    assert router.finalize(values).status == "retry"
    assert router.finalize(values, retries_used=2).status == "review"


@pytest.mark.parametrize("stage", ["finalize", "voice"])
def test_invalid_session_is_always_high_priority_review(router, stage):
    decision = getattr(router, stage)(results(), session_valid=False)
    assert decision.status == "review" and decision.priority == "high"


@pytest.mark.parametrize("module", [Module.VOICE_CHALLENGE, Module.VOICE_SPOOF, Module.LIPSYNC])
@pytest.mark.parametrize("status", [Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE])
def test_unusable_required_voice_module_never_passes(router, module, status):
    values = replace_result(results(), module, status=status, error_code=ErrorCode.E_TIMEOUT)
    assert router.voice(values).status == "review"


@pytest.mark.parametrize("module", [Module.VOICE_CHALLENGE, Module.VOICE_SPOOF, Module.LIPSYNC])
def test_missing_required_voice_module_requires_review(router, module):
    values = results()
    del values[module]
    assert router.voice(values).status == "review"


@pytest.mark.parametrize("module", [Module.VOICE_SPOOF, Module.LIPSYNC])
def test_missing_voice_probability_cannot_fallback_to_raw_score(router, module):
    values = replace_result(results(), module, prob_attack=None, score=0)
    assert router.voice(values).status == "review"


def test_wrong_phrase_has_only_one_reread_but_unclear_is_review(router):
    values = replace_result(
        results(), Module.VOICE_CHALLENGE, gate=Gate.FAIL, error_code=ErrorCode.E_CHALLENGE_MISMATCH
    )
    assert router.voice(values, rereads_used=0).status == "voice_challenge"
    assert router.voice(values, rereads_used=1).status == "review"
    replace_result(values, Module.VOICE_CHALLENGE, gate=Gate.UNCLEAR)
    assert router.voice(values, rereads_used=0).status == "review"


@pytest.mark.parametrize("probability,expected", [(0.15, "pass"), (0.150001, "review")])
def test_voice_probability_threshold_is_inclusive(router, probability, expected):
    values = results()
    for module in (Module.VOICE_SPOOF, Module.LIPSYNC):
        replace_result(values, module, prob_attack=probability)
    assert router.voice(values).status == expected


def test_voice_challenge_wer_is_not_fused_as_attack_probability(router):
    values = replace_result(
        results(), Module.VOICE_CHALLENGE, gate=Gate.PASS, score=0.95, prob_attack=None
    )
    assert router.voice(values).status == "pass"


@pytest.mark.parametrize("where", ["context", "evidence"])
def test_positive_splice_flag_requires_review(router, where):
    values = results()
    if where == "context":
        decision = router.voice(values, splice_flags=1)
    else:
        evidence = [
            *values[Module.VOICE_CHALLENGE].evidence,
            Evidence(type="scalar", name="splice_flags", value=1),
        ]
        replace_result(values, Module.VOICE_CHALLENGE, evidence=evidence)
        decision = router.voice(values)
    assert decision.status == "review"


def test_policy_does_not_mutate_results_or_counters(router):
    values = results("low_quality")
    snapshot = deepcopy({key: value.model_dump() for key, value in values.items()})
    first = router.finalize(values, retries_used=1)
    second = router.finalize(values, retries_used=1)
    assert first.status == second.status == "retry"
    assert {key: value.model_dump() for key, value in values.items()} == snapshot


def test_voice_threshold_is_separate_from_face_b_and_yaml_metadata_tracks_content(tmp_path):
    source = Path(__file__).parents[1] / "configs/thresholds.yaml"
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    raw["face"]["b"] = 0.10
    raw["voice"]["spoof_threshold"] = 0.20
    path = tmp_path / "thresholds.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config = load_config(path)
    assert config.face.b == 0.10 and config.voice.spoof_threshold == 0.20
    assert config.voice.max_syllable_wer == 0.3
    assert config.voice.min_unaccented_similarity == 0.9
    router = TrustRouter(config)
    values = results()
    for module in (Module.VOICE_SPOOF, Module.LIPSYNC):
        replace_result(values, module, prob_attack=0.15)
    assert router.voice(values).status == "pass"
    before = config.config_version
    raw["voice"]["spoof_threshold"] = 0.11
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    changed = load_config(path)
    assert changed.config_version != before
    assert TrustRouter(changed).voice(values).status == "review"


@pytest.mark.parametrize("ood,expected", [(True, "review"), (False, "pass"), (None, "pass")])
def test_ood_gate_only_blocks_when_explicitly_out_of_distribution(router, ood, expected):
    assert router.finalize(results(), ood=ood).status == expected


def test_missing_optional_splice_evidence_is_not_required_for_voice_pass(router):
    values = results()
    evidence = [
        item for item in values[Module.VOICE_CHALLENGE].evidence if item.name != "splice_flags"
    ]
    replace_result(values, Module.VOICE_CHALLENGE, evidence=evidence)
    assert router.voice(values, splice_flags=None).status == "pass"
