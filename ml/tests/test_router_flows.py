"""Purpose policy must preserve every required gate, including missing/error/degraded."""

import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module, Status
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.router.flows import route_face, route_voice
from vericlue_ml.router.policy import TrustRouter


def results(scenario="genuine"):
    inp = DetectorInput(metadata={"scenario": scenario})
    return {module: MockDetector(module).predict(inp) for module in Module}


@pytest.mark.parametrize("purpose", ["onboarding", "recovery"])
def test_registration_and_recovery_always_require_voice(purpose):
    router = TrustRouter()
    assert route_face(router.finalize(results()), purpose).status == "voice_challenge"
    assert route_voice(router.voice(results()), purpose).status == "pass"


@pytest.mark.parametrize("purpose", ["onboarding", "recovery", "reauth"])
@pytest.mark.parametrize(
    "module",
    [Module.QUALITY, Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.CHROMAPULSE, Module.CAMPROBE],
)
@pytest.mark.parametrize("status", [None, Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE])
def test_failed_required_face_gate_never_passes(purpose, module, status):
    values = results()
    if status is None:
        del values[module]
    else:
        values[module] = values[module].model_copy(update={"status": status})
    decision = TrustRouter().finalize(values)
    expected = "deny" if purpose == "reauth" else "review"
    assert route_face(decision, purpose, device_verified=True).status == expected


@pytest.mark.parametrize("purpose", ["onboarding", "recovery", "reauth"])
@pytest.mark.parametrize("module", [Module.VOICE_CHALLENGE, Module.VOICE_SPOOF, Module.LIPSYNC])
@pytest.mark.parametrize("status", [None, Status.ERROR, Status.DEGRADED])
def test_failed_required_voice_gate_never_passes(purpose, module, status):
    values = results()
    if status is None:
        del values[module]
    else:
        values[module] = values[module].model_copy(update={"status": status})
    decision = TrustRouter().voice(values)
    assert route_voice(decision, purpose).status == ("deny" if purpose == "reauth" else "review")


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("genuine", "pass"),
        ("voice_clone", "voice_challenge"),
        ("print", "deny"),
        ("low_quality", "deny"),
    ],
)
def test_verified_reauth_routes_face_result(scenario, expected):
    decision = TrustRouter().finalize(results(scenario))
    assert route_face(decision, "reauth", device_verified=True).status == expected
    assert route_face(decision, "reauth").status == "recovery_required"


def test_legacy_policy_unchanged_and_unknown_purpose_is_not_accepted():
    decision = TrustRouter().finalize(results())
    assert route_face(decision, None) is decision
    with pytest.raises(ValueError):
        route_face(decision, "typo")
    with pytest.raises(ValueError):
        route_voice(decision, "typo")
