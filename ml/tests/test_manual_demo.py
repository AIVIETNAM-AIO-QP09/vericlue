"""Manual cutoffs demonstrate raw inference; they do not supply calibrated probabilities."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from vericlue_ml.common.manual_demo import ManualDemoThresholds
from vericlue_ml.common.result import Evidence, ModuleResult


@pytest.mark.parametrize("module", ["face_pad", "face_deepfake"])
def test_manual_attack_cutoff_requires_successful_raw_inference(module):
    policy = ManualDemoThresholds(pad_max=0.4, gend_max=0.6)
    raw = ModuleResult(
        module=module, model_version="real-backend", status="ok", score=0.35, latency_ms=0
    )
    assert policy.accepts_attack(raw)
    assert not policy.accepts_attack(raw.model_copy(update={"status": "degraded"}))
    assert not policy.accepts_attack(raw.model_copy(update={"status": "error"}))
    assert not policy.accepts_attack(raw.model_copy(update={"error_code": "E_INTERNAL"}))
    assert not policy.accepts_attack(raw.model_copy(update={"score": None}))
    assert not policy.accepts_attack(raw.model_copy(update={"score": float("nan")}))
    assert not policy.accepts_attack(raw.model_copy(update={"score": 0.9}))


def test_manual_deepfake_three_view_checks_frontal_score_and_all_views_valid():
    policy = ManualDemoThresholds(gend_max=0.50)
    res = ModuleResult(
        module="face_deepfake",
        model_version="gend-clip-l14+headturn-3views-v1",
        status="ok",
        score=0.75,
        evidence=[
            Evidence(
                type="timeseries",
                name="view_scores",
                value={"front": 0.35, "left": 0.75, "right": 0.51},
            )
        ],
        latency_ms=0,
    )
    assert policy.accepts_attack(res)
    high_front = res.model_copy(
        update={
            "evidence": [
                Evidence(
                    type="timeseries",
                    name="view_scores",
                    value={"front": 0.55, "left": 0.40, "right": 0.40},
                )
            ]
        }
    )
    assert not policy.accepts_attack(high_front)
    missing_view = res.model_copy(
        update={
            "evidence": [
                Evidence(
                    type="timeseries",
                    name="view_scores",
                    value={"front": 0.35, "left": 0.40},
                )
            ]
        }
    )
    assert not policy.accepts_attack(missing_view)


def test_policy_binding_changes_with_cutoffs_and_rejects_invalid_values():
    policy = ManualDemoThresholds()
    assert len(policy.policy_id) == 64
    assert policy.policy_id != ManualDemoThresholds(match_min=0.4).policy_id
    for value in [0, 1, float("nan"), float("inf")]:
        with pytest.raises(ValidationError):
            ManualDemoThresholds(pad_max=value)


@pytest.mark.parametrize("score,expected", [(0.2, "pass"), (0.8, "fail")])
def test_attack_adapter_uses_manual_gate_without_fabricating_probability(
    monkeypatch, score, expected
):
    from test_session_attack import attack_input

    from vericlue_ml.face import session_attack

    backend = SimpleNamespace(
        name="face_pad",
        frames_version="real-pad-views",
        predict_frames=lambda *_: ModuleResult(
            module="face_pad",
            model_version="real-pad-views",
            status="ok",
            score=score,
            latency_ms=0,
        ),
    )
    monkeypatch.setattr(session_attack, "session_views", lambda *_: ({}, "a" * 64))
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "a" * 64)
    policy = ManualDemoThresholds()
    result = session_attack.SessionAttackDetector(
        backend, SimpleNamespace(), manual_demo=policy
    ).predict(attack_input(video=Path("synthetic.mp4")))
    assert result.status == "ok" and result.gate == expected
    assert result.prob_attack is None
    assert result.quality["calibrated"] is False
    assert result.quality["demo_policy_id"] == policy.policy_id
    assert result.model_version.endswith(policy.version_suffix)


@pytest.mark.parametrize("same", [True, False])
def test_manual_identity_uses_raw_cosines_without_fake_calibration(tmp_path, monkeypatch, same):
    from test_face_match import setup_detector, vector

    monkeypatch.delenv("FACE_MATCH_CALIBRATION", raising=False)
    detector, inp = setup_detector(
        tmp_path, vectors=[vector(), vector(0 if same else 1), vector(), vector()]
    )
    detector.manual_demo = ManualDemoThresholds()
    result = detector.predict(inp)
    assert result.status == "ok"
    assert result.gate == ("pass" if same else "fail")
    assert result.prob_attack is None
    assert result.quality["calibrated"] is False
    assert result.model_version.endswith(detector.manual_demo.version_suffix)


def test_manual_voice_spoof_rejects_degraded_error_unmeasured_and_diagnostic_results():
    policy = ManualDemoThresholds()
    ok_window = {
        "start_sample": 0,
        "end_sample": 64000,
        "start_s": 0.0,
        "end_s": 4.0,
        "result": {
            "module": "voice_spoof",
            "model_version": "nes2net-x@first4s",
            "status": "ok",
            "gate": "pass",
            "score": -2.5,
            "quality": {"diagnostic_only": False},
            "latency_ms": 10.0,
        },
    }
    valid_timeline = ModuleResult(
        module="voice_spoof",
        model_version="nes2net-x@timeline",
        status="ok",
        gate="pass",
        quality={
            "diagnostic_only": False,
            "planned_windows": 1,
            "measured_windows": 1,
            "low_quality_windows": 0,
            "error_windows": 0,
            "all_source_samples_measured": True,
        },
        evidence=[Evidence(type="segments", name="nes2net_windows", value=[ok_window])],
        latency_ms=10.0,
    )
    assert not policy.accepts_voice_spoof(valid_timeline)

    # Degraded outer status (current uncalibrated NES2Net diagnostic output) must be rejected.
    assert not policy.accepts_voice_spoof(
        valid_timeline.model_copy(update={"status": "degraded", "gate": "unclear"})
    )
    assert not policy.accepts_voice_spoof(
        valid_timeline.model_copy(update={"status": "error", "error_code": "E_INTERNAL"})
    )
    assert not policy.accepts_voice_spoof(
        valid_timeline.model_copy(
            update={"quality": {**valid_timeline.quality, "diagnostic_only": True}}
        )
    )
    assert not policy.accepts_voice_spoof(
        valid_timeline.model_copy(update={"model_version": "mock@0.1"})
    )

    # Unmeasured / not_applicable windows must never be ignored.
    partial_window = {
        **ok_window,
        "start_sample": 64000,
        "end_sample": 80000,
        "result": {
            **ok_window["result"],
            "status": "not_applicable",
            "error_code": "E_LOW_QUALITY",
            "gate": "unclear",
            "score": None,
        },
    }
    assert not policy.accepts_voice_spoof(
        valid_timeline.model_copy(
            update={
                "quality": {
                    **valid_timeline.quality,
                    "planned_windows": 2,
                    "measured_windows": 1,
                    "low_quality_windows": 1,
                    "all_source_samples_measured": False,
                },
                "evidence": [
                    Evidence(
                        type="segments",
                        name="nes2net_windows",
                        value=[ok_window, partial_window],
                    )
                ],
            }
        )
    )

    # Degraded inner window or high spoof score must be rejected.
    degraded_inner = {
        **ok_window,
        "result": {**ok_window["result"], "status": "degraded", "gate": "unclear"},
    }
    assert not policy.accepts_voice_spoof(
        valid_timeline.model_copy(
            update={
                "evidence": [
                    Evidence(type="segments", name="nes2net_windows", value=[degraded_inner])
                ]
            }
        )
    )
    high_score_inner = {
        **ok_window,
        "result": {**ok_window["result"], "score": 3.5},
    }
    assert not policy.accepts_voice_spoof(
        valid_timeline.model_copy(
            update={
                "evidence": [
                    Evidence(type="segments", name="nes2net_windows", value=[high_score_inner])
                ]
            }
        )
    )
