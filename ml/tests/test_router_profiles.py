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
MVP_RUN_VOICE = (*MVP_VOICE, Module.LIPSYNC)
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
    assert router.profile.advisory_voice_modules == ()
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
    assert router.profile.advisory_voice_modules == (Module.LIPSYNC,)
    assert router.profile.finalize_modules == MVP_FINALIZE
    assert router.profile.voice_step_modules == MVP_RUN_VOICE
    assert router.profile.required_voice_step_modules == MVP_VOICE
    assert Module.LIPSYNC in router.profile.modules
    assert set(router.profile.calibration_modules) == {*FACE, Module.VOICE_SPOOF}


@pytest.mark.parametrize(
    "profile,stage,modules,module",
    [(profile, stage, modules, module) for profile, stage, modules in STAGES for module in modules],
)
@pytest.mark.parametrize(
    "failure", ["missing", Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE]
)
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


def test_full_still_requires_chromapulse_while_mvp_omits_it():
    values = mock_results(MVP_FINALIZE)
    assert TrustRouter(profile="mvp").finalize(values).status == "pass"
    assert TrustRouter(profile="full").finalize(values).status == "review"


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


@pytest.mark.parametrize("where", ["context", "challenge", "lipsync"])
@pytest.mark.parametrize("flag", [1, "bad", float("nan"), True])
def test_mvp_preserves_splice_checks(where, flag):
    values = mock_results(MVP_RUN_VOICE)
    if where != "context":
        module = Module.LIPSYNC if where == "lipsync" else Module.VOICE_CHALLENGE
        values[module] = values[module].model_copy(
            update={"evidence": [Evidence(type="scalar", name="splice_flags", value=flag)]}
        )
        decision = TrustRouter(profile="mvp").voice(values)
    else:
        decision = TrustRouter(profile="mvp").voice(values, splice_flags=flag)
    assert decision.status == "review"
    if flag == 1 and not isinstance(flag, bool):
        assert decision.priority == "high"


@pytest.mark.parametrize(
    "lip_condition",
    [
        "missing",
        Status.ERROR,
        Status.DEGRADED,
        Status.NOT_APPLICABLE,
        "timeout",
        "high",
        "uncalibrated",
    ],
)
def test_mvp_lipsync_is_still_returned_but_cannot_veto_good_required_voice(lip_condition):
    values = mock_results(MVP_RUN_VOICE)
    if lip_condition == "missing":
        del values[Module.LIPSYNC]
    else:
        changes = {}
        if lip_condition == "high":
            changes = {"score": 1.0, "prob_attack": 1.0}
        elif lip_condition == "uncalibrated":
            changes = {"model_version": "real@without-artifact", "score": 1.0, "prob_attack": None}
        elif lip_condition == "timeout":
            changes = {"status": Status.ERROR, "error_code": "E_TIMEOUT", "prob_attack": None}
        else:
            changes = {"status": lip_condition, "prob_attack": None}
        values[Module.LIPSYNC] = values[Module.LIPSYNC].model_copy(update=changes)
    snapshot = {module: result.model_dump() for module, result in values.items()}
    decision = TrustRouter(profile="mvp").voice(values)
    assert decision.status == "pass"
    expected = dict(snapshot)
    if Module.LIPSYNC in values:
        expected[Module.LIPSYNC] = {
            **snapshot[Module.LIPSYNC],
            "evidence": [
                *snapshot[Module.LIPSYNC]["evidence"],
                Evidence(
                    type="text",
                    name="decision_role",
                    value="advisory",
                    label_vi="Khớp môi chỉ tham khảo ở chế độ MVP",
                ).model_dump(),
            ],
        }
    assert {module: result.model_dump() for module, result in decision.results.items()} == expected
    assert {module: result.model_dump() for module, result in values.items()} == snapshot
    assert TrustRouter(profile="full").voice(values).status == "review"


@pytest.mark.parametrize("stage", ["finalize", "voice"])
def test_advisory_result_role_is_nonmutating_deduplicated_and_only_mvp(stage):
    values = mock_results(tuple(Module))
    snapshot = {module: result.model_dump() for module, result in values.items()}
    router = TrustRouter(profile="mvp")
    first = getattr(router, stage)(values)
    second = getattr(router, stage)(first.results)
    roles = [
        evidence
        for evidence in second.results[Module.LIPSYNC].evidence
        if evidence.name == "decision_role"
    ]
    assert len(roles) == 1
    assert roles[0].value == "advisory"
    assert roles[0].label_vi == "Khớp môi chỉ tham khảo ở chế độ MVP"
    assert {module: result.model_dump() for module, result in values.items()} == snapshot
    full = getattr(TrustRouter(profile="full"), stage)(values)
    assert {module: result.model_dump() for module, result in full.results.items()} == snapshot


@pytest.mark.parametrize("profile", ["full", "mvp"])
@pytest.mark.parametrize("flag", [1, "bad", float("nan"), True])
@pytest.mark.parametrize("rereads_used,expected", [(0, "voice_challenge"), (1, "review")])
def test_wrong_phrase_precedes_lipsync_splice_flags_and_other_module_errors(
    profile, flag, rereads_used, expected
):
    values = mock_results(MVP_RUN_VOICE)
    values[Module.VOICE_CHALLENGE] = values[Module.VOICE_CHALLENGE].model_copy(
        update={"gate": Gate.FAIL}
    )
    for module in (Module.VOICE_SPOOF, Module.LIPSYNC):
        values[module] = values[module].model_copy(update={"status": Status.ERROR})
    values[Module.LIPSYNC] = values[Module.LIPSYNC].model_copy(
        update={"evidence": [Evidence(type="scalar", name="splice_flags", value=flag)]}
    )
    decision = TrustRouter(profile=profile).voice(values, rereads_used=rereads_used)
    assert decision.status == expected
    assert decision.priority == "normal"
    assert decision.reason == "phrase mismatch"


@pytest.mark.parametrize("profile", ["full", "mvp"])
@pytest.mark.parametrize(
    "condition", ["missing", Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE, "unclear"]
)
def test_only_usable_matched_challenge_can_make_splice_flags_high_priority(profile, condition):
    values = mock_results(MVP_RUN_VOICE)
    values[Module.LIPSYNC] = values[Module.LIPSYNC].model_copy(
        update={"evidence": [Evidence(type="scalar", name="splice_flags", value=1)]}
    )
    if condition == "missing":
        del values[Module.VOICE_CHALLENGE]
    else:
        changes = {"gate": Gate.UNCLEAR} if condition == "unclear" else {"status": condition}
        values[Module.VOICE_CHALLENGE] = values[Module.VOICE_CHALLENGE].model_copy(update=changes)
    decision = TrustRouter(profile=profile).voice(values)
    assert decision.status == "review"
    assert decision.priority == "normal"


@pytest.mark.parametrize("profile", ["full", "mvp"])
def test_matched_challenge_still_uses_advisory_lipsync_splice_evidence(profile):
    values = mock_results(MVP_RUN_VOICE)
    values[Module.LIPSYNC] = values[Module.LIPSYNC].model_copy(
        update={
            "status": Status.DEGRADED,
            "evidence": [Evidence(type="scalar", name="splice_flags", value=1)],
        }
    )
    decision = TrustRouter(profile=profile).voice(values)
    assert decision.status == "review" and decision.priority == "high"


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
