"""Luật quyết định TẠM theo bảng kịch bản mock (dùng lại cho PLAT-09). ROUT-02 sẽ thay luật."""

from __future__ import annotations

import pytest

from vericlue_api.core.config import Settings
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.provisional_decision import (
    FINALIZE_MODULES,
    VOICE_STEP_MODULES,
    decide_finalize,
    decide_voice,
)
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status

S = Settings()
B, A = S.provisional_threshold_b, S.provisional_threshold_a


def test_provisional_thresholds_are_the_agreed_values():
    assert (B, A) == (0.15, 0.60)


def finalize(scenario: str, retries_used: int = 0, results=None):
    results = results or run_detectors(FINALIZE_MODULES, session_id="t", scenario=scenario)
    return decide_finalize(results, retries_used=retries_used, max_retries=2, b=B, a=A)


def voice(scenario: str, rereads_used: int = 0):
    results = run_detectors(VOICE_STEP_MODULES, session_id="t", scenario=scenario)
    return decide_voice(results, rereads_used=rereads_used, b=B)


@pytest.mark.parametrize(
    ("scenario", "status"),
    [
        ("genuine", "pass"),
        ("print", "review"),
        ("replay", "review"),
        ("faceswap", "review"),
        ("virtual_cam", "review"),
        ("voice_clone", "voice_challenge"),
        ("low_quality", "retry"),
        ("error", "review"),
    ],
)
def test_finalize_by_scenario(scenario, status):
    assert finalize(scenario).status == status


def test_virtual_cam_is_high_priority():
    assert finalize("virtual_cam").priority == "high"
    assert finalize("genuine").priority == "normal"


def test_low_quality_retries_twice_then_review():
    first, second, third = (finalize("low_quality", n) for n in (0, 1, 2))
    assert (first.status, second.status, third.status) == ("retry", "retry", "review")
    assert first.retry_hint == "MORE_LIGHT"


def test_voice_clone_goes_to_voice_challenge_then_review():
    assert finalize("voice_clone").status == "voice_challenge"
    assert voice("voice_clone").status == "review"


def test_genuine_voice_passes():
    assert voice("genuine").status == "pass"


def test_error_scenario_never_passes():
    assert finalize("error").status == "review"
    assert voice("error").status == "review"


def _replace(results, module, **changes):
    results = dict(results)
    results[module] = results[module].model_copy(update=changes)
    return results


def test_voice_clone_face_probability_is_in_the_middle_band():
    results = run_detectors(FINALIZE_MODULES, session_id="t", scenario="voice_clone")
    probs = [results[m].prob_attack for m in (Module.FACE_PAD, Module.FACE_DEEPFAKE)]
    assert B <= max(probs) < A


@pytest.mark.parametrize("module", [Module.FACE_PAD, Module.FACE_DEEPFAKE])
@pytest.mark.parametrize("status", [Status.DEGRADED, Status.ERROR, Status.NOT_APPLICABLE])
def test_unusable_face_module_never_passes(module, status):
    base = run_detectors(FINALIZE_MODULES, session_id="t", scenario="genuine")
    assert finalize("genuine", results=_replace(base, module, status=status)).status == "review"


@pytest.mark.parametrize("module", [Module.QUALITY, Module.CHROMAPULSE, Module.CAMPROBE])
@pytest.mark.parametrize("status", [Status.DEGRADED, Status.ERROR])
def test_unusable_required_gate_never_passes(module, status):
    base = run_detectors(FINALIZE_MODULES, session_id="t", scenario="genuine")
    assert finalize("genuine", results=_replace(base, module, status=status)).status == "review"


def test_missing_module_never_passes():
    base = run_detectors(FINALIZE_MODULES, session_id="t", scenario="genuine")
    del base[Module.FACE_DEEPFAKE]
    assert finalize("genuine", results=base).status == "review"


@pytest.mark.parametrize(
    ("prob", "status"),
    [
        (0.0, "pass"),
        (B - 0.001, "pass"),
        (B, "voice_challenge"),
        (A - 0.001, "voice_challenge"),
        (A, "review"),
        (0.99, "review"),
    ],
)
def test_threshold_boundaries_use_max_of_face_modules(prob, status):
    base = run_detectors(FINALIZE_MODULES, session_id="t", scenario="genuine")
    results = _replace(base, Module.FACE_PAD, prob_attack=prob)
    assert finalize("genuine", results=results).status == status


def test_presence_unclear_retries_with_brightness_hint_then_review():
    base = run_detectors(FINALIZE_MODULES, session_id="t", scenario="genuine")
    results = _replace(base, Module.CHROMAPULSE, gate=Gate.UNCLEAR)
    out = finalize("genuine", results=results)
    assert (out.status, out.retry_hint) == ("retry", "BRIGHTNESS_UP")
    assert finalize("genuine", retries_used=2, results=results).status == "review"


def test_wrong_sentence_allows_one_reread_then_review():
    base = run_detectors(VOICE_STEP_MODULES, session_id="t", scenario="genuine")
    wrong = _replace(base, Module.VOICE_CHALLENGE, gate=Gate.FAIL)
    assert decide_voice(wrong, rereads_used=0, b=B).status == "voice_challenge"
    assert decide_voice(wrong, rereads_used=1, b=B).status == "review"


def test_detector_exception_becomes_error_and_never_passes(monkeypatch):
    def boom(_name):
        raise RuntimeError("model crashed")

    monkeypatch.setattr("vericlue_api.services.detection.get_detector", boom)
    results = run_detectors(FINALIZE_MODULES, session_id="t", scenario="genuine")
    assert all(isinstance(r, ModuleResult) and r.status == Status.ERROR for r in results.values())
    assert finalize("genuine", results=results).status == "review"
