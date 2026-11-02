"""Optional server motion modules are mandatory signals when enabled, independent of UI."""

import pytest
from test_dynamic_flows import create, submit_face

from vericlue_ml.common.result import Evidence, Module, ModuleResult


@pytest.mark.parametrize(
    "status,gate,expected",
    [
        ("ok", "pass", "pass"),  # onboarding with a clear face: no sentence
        ("degraded", "pass", "review"),
        ("error", "pass", "review"),
        ("ok", "fail", "review"),
        ("ok", "unclear", "review"),
    ],
)
def test_motion_failures_cannot_be_accepted(client, status, gate, expected):
    root = client.app.state.vericlue
    root.settings.session_face_checks = True
    seen = []

    class Motion:
        def __init__(self, module):
            self.module = module

        def predict(self, inp):
            assert inp.metadata["expected_challenge"]["dynamic"]["session_id"] == inp.session_id
            assert (
                inp.metadata["challenge_id"] == inp.metadata["expected_challenge"]["challenge_id"]
            )
            seen.append(self.module)
            return ModuleResult(
                module=self.module,
                model_version="synthetic-motion",
                status=status,
                gate=gate,
                latency_ms=0,
            )

    for module in (Module.GAZE_TRACKING, Module.HEAD_TURN):
        root.orchestrator._detectors[module] = Motion(module)
    created, auth = create(client)
    result = submit_face(client, created, auth)
    assert result["status"] == expected
    assert set(seen) == {Module.GAZE_TRACKING, Module.HEAD_TURN}
    with root.transaction() as state:
        assert {Module.GAZE_TRACKING, Module.HEAD_TURN} <= state.sessions.get(
            created["session_id"]
        ).results.keys()


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "head_error",
        "gaze_failed",
        "face_error",
        "attack",
        "calibration_missing",
        "attack_probability",
    ],
)
def test_pose_capture_retry_is_bounded_and_never_clears_other_failures(client, fault, monkeypatch):
    root = client.app.state.vericlue
    root.settings.session_face_checks = True
    if fault == "attack_probability":
        monkeypatch.setattr(
            "vericlue_ml.common.calibration.CalibrationStore.apply", lambda self, result: result
        )

    class Measured:
        def __init__(self, module):
            self.module = module

        def predict(self, inp):
            if self.module == Module.HEAD_TURN:
                return ModuleResult(
                    module=self.module,
                    model_version="synthetic-head",
                    latency_ms=0,
                    status="error" if fault == "head_error" else "degraded",
                    gate="unclear",
                    evidence=[Evidence(type="text", name="head_reason", value="pose_out_of_range")],
                )
            if self.module == Module.GAZE_TRACKING:
                return ModuleResult(
                    module=self.module,
                    model_version="synthetic-gaze",
                    latency_ms=0,
                    status="ok",
                    gate="fail" if fault == "gaze_failed" else "pass",
                )
            if fault == "calibration_missing":
                return ModuleResult(
                    module=self.module,
                    model_version="synthetic-no-artifact",
                    latency_ms=0,
                    status="ok",
                    gate="unclear",
                    score=0.1,
                )
            if fault == "attack_probability" and self.module == Module.FACE_PAD:
                return ModuleResult(
                    module=self.module,
                    model_version="synthetic-high-risk",
                    latency_ms=0,
                    status="ok",
                    gate="unclear",
                    prob_attack=1.0,
                )
            return ModuleResult(
                module=self.module,
                model_version="synthetic-views",
                latency_ms=0,
                status="error" if fault == "face_error" else "degraded",
                gate="fail" if fault == "attack" else "unclear",
                error_code="E_LOW_QUALITY",
            )

    for module in (Module.HEAD_TURN, Module.GAZE_TRACKING, Module.FACE_PAD, Module.FACE_DEEPFAKE):
        root.orchestrator._detectors[module] = Measured(module)
    created, auth = create(client)
    result = submit_face(client, created, auth)
    if fault is not None:
        assert result["status"] == "review"
        return
    assert result["status"] == "retry"
    assert result["retry_hint"] == "HOLD_STILL"
    assert result["challenge"]["challenge_id"] != created["challenge"]["challenge_id"]
    with root.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert session.video is None and not session.results and not session.accepted_steps
    # Exactly one pose-quality retry; repeated bad capture returns review.
    repeated = submit_face(client, created, auth, result["challenge"])
    assert repeated["status"] == "review"
