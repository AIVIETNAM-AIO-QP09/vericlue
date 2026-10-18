"""ROUT-01: profile-specific mandatory gates and fail-closed calibration."""

from pathlib import Path

import pytest

from vericlue_ml.common.calibration import CalibrationStore
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Evidence, Gate, Module, Status
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.router.policy import TrustRouter

FACE = (Module.FACE_PAD, Module.FACE_DEEPFAKE)
FULL_FINALIZE = (Module.QUALITY, *FACE, Module.CHROMAPULSE, Module.CAMPROBE)
MVP_FINALIZE = (Module.QUALITY, *FACE, Module.CAMPROBE)
FULL_VOICE = (Module.VOICE_CHALLENGE, Module.VOICE_SPOOF, Module.LIPSYNC)
MVP_VOICE = (Module.VOICE_CHALLENGE, Module.VOICE_SPOOF)
STAGES = [
    ("full", "finalize", FULL_FINALIZE),
    ("full", "voice", FULL_VOICE),
    ("mvp", "finalize", MVP_FINALIZE),
    ("mvp", "voice", MVP_VOICE),
]


def mock_results(modules, scenario="genuine"):
    inputs = DetectorInput(metadata={"scenario": scenario})
    return {module: MockDetector(module).predict(inputs) for module in modules}


@pytest.mark.parametrize("profile,stage,modules", STAGES)
def test_each_profile_passes_with_only_its_required_mock_modules(profile, stage, modules):
    router = TrustRouter(profile=profile)
    assert getattr(router, stage)(mock_results(modules)).status == "pass"


def test_default_profile_retains_full_module_requirements():
    router = TrustRouter()
    assert router.profile.presence_modules == (Module.CHROMAPULSE, Module.CAMPROBE)
    assert router.profile.voice_modules == (Module.VOICE_SPOOF, Module.LIPSYNC)
    assert router.profile.finalize_modules == FULL_FINALIZE
    assert router.profile.voice_step_modules == FULL_VOICE
    assert set(router.profile.calibration_modules) == {
        *FACE,
        Module.VOICE_SPOOF,
        Module.LIPSYNC,
    }


def test_mvp_profile_omits_auxiliary_modules_and_calibrators():
    router = TrustRouter(profile="mvp")
    assert router.profile.presence_modules == (Module.CAMPROBE,)
    assert router.profile.voice_modules == (Module.VOICE_SPOOF,)
    assert router.profile.finalize_modules == MVP_FINALIZE
    assert router.profile.voice_step_modules == MVP_VOICE
    assert set(router.profile.calibration_modules) == {*FACE, Module.VOICE_SPOOF}


@pytest.mark.parametrize(
    "profile,stage,modules,module",
    [(profile, stage, modules, module) for profile, stage, modules in STAGES for module in modules],
)
@pytest.mark.parametrize("failure", ["missing", Status.ERROR, Status.DEGRADED])
def test_every_required_module_failure_reviews_at_reached_gate(
    profile, stage, modules, module, failure
):
    values = mock_results(modules)
    if failure == "missing":
        del values[module]
    else:
        values[module] = values[module].model_copy(update={"status": failure, "prob_attack": 0})
    assert getattr(TrustRouter(profile=profile), stage)(values).status == "review"


@pytest.mark.parametrize(
    "profile,stage,modules,module",
    [
        (profile, stage, modules, module)
        for profile, stage, modules in STAGES
        for module in modules
        if module in (*FACE, Module.VOICE_SPOOF, Module.LIPSYNC)
    ],
)
def test_missing_real_calibrator_cannot_use_existing_probability(profile, stage, modules, module):
    values = mock_results(modules)
    values[module] = values[module].model_copy(
        update={"model_version": "real@uncalibrated", "score": 0.01, "prob_attack": 0.0}
    )
    missing_root = Path(__file__).parent / "fixtures" / "absent_calibrators"
    router = TrustRouter(profile=profile, calibrators=CalibrationStore(root=missing_root))
    decision = getattr(router, stage)(values)
    assert decision.status == "review"
    assert decision.results[module].status == Status.ERROR
    assert decision.results[module].prob_attack is None
    assert values[module].prob_attack == 0.0


@pytest.mark.parametrize("stage,modules", [("finalize", MVP_FINALIZE), ("voice", MVP_VOICE)])
def test_full_still_requires_chromapulse_and_lipsync(stage, modules):
    values = mock_results(modules)
    assert getattr(TrustRouter(profile="mvp"), stage)(values).status == "pass"
    assert getattr(TrustRouter(profile="full"), stage)(values).status == "review"


def test_mvp_challenge_remains_a_gate_and_allows_one_reread():
    router = TrustRouter(profile="mvp")
    values = mock_results(MVP_VOICE)
    challenge = values[Module.VOICE_CHALLENGE]
    values[Module.VOICE_CHALLENGE] = challenge.model_copy(update={"gate": Gate.FAIL})
    assert router.voice(values).status == "voice_challenge"
    assert router.voice(values, rereads_used=1).status == "review"
    values[Module.VOICE_CHALLENGE] = challenge.model_copy(update={"gate": Gate.UNCLEAR})
    assert router.voice(values).status == "review"
    values[Module.VOICE_CHALLENGE] = challenge.model_copy(
        update={"gate": Gate.PASS, "score": 1.0, "prob_attack": None}
    )
    assert router.voice(values).status == "pass"


@pytest.mark.parametrize("where", ["context", "evidence"])
@pytest.mark.parametrize("flag", [1, "bad", float("nan"), True])
def test_mvp_preserves_splice_checks(where, flag):
    values = mock_results(MVP_VOICE)
    if where == "evidence":
        values[Module.VOICE_CHALLENGE] = values[Module.VOICE_CHALLENGE].model_copy(
            update={"evidence": [Evidence(type="scalar", name="splice_flags", value=flag)]}
        )
        decision = TrustRouter(profile="mvp").voice(values)
    else:
        decision = TrustRouter(profile="mvp").voice(values, splice_flags=flag)
    assert decision.status == "review"
    if flag == 1 and not isinstance(flag, bool):
        assert decision.priority == "high"


def test_mvp_camprobe_failure_is_high_priority_and_unclear_respects_retry_limit():
    router = TrustRouter(profile="mvp")
    values = mock_results(MVP_FINALIZE)
    camprobe = values[Module.CAMPROBE]
    values[Module.CAMPROBE] = camprobe.model_copy(update={"gate": Gate.FAIL})
    decision = router.finalize(values)
    assert decision.status == "review" and decision.priority == "high"
    values[Module.CAMPROBE] = camprobe.model_copy(update={"gate": Gate.UNCLEAR})
    assert router.finalize(values).status == "retry"
    assert router.finalize(values, retries_used=2).status == "review"


@pytest.mark.parametrize("profile", ["full", "mvp"])
def test_quality_retry_still_precedes_face_failure_in_both_profiles(profile):
    modules = FULL_FINALIZE if profile == "full" else MVP_FINALIZE
    values = mock_results(modules, scenario="low_quality")
    router = TrustRouter(profile=profile)
    assert router.finalize(values).status == "retry"
    assert router.finalize(values, retries_used=2).status == "review"
