"""Synthetic fitted classifiers do not replace independent motion/security gates."""

from types import SimpleNamespace

import pytest
from test_dynamic_flows import create, submit_face

from vericlue_ml.common.calibration import CalibFit, CalibrationStore, fit
from vericlue_ml.common.result import Module, ModuleResult
from vericlue_ml.face import session_attack
from vericlue_ml.face.session_attack import SessionAttackDetector


@pytest.mark.parametrize(
    "motion_status,expected", [("ok", "pass"), ("degraded", "review"), ("error", "review")]
)
def test_fitted_classifiers_cannot_clear_a_failed_mandatory_motion(
    client, monkeypatch, tmp_path, motion_status, expected
):
    root = client.app.state.vericlue
    root.settings.session_face_checks = True
    store = CalibrationStore(tmp_path)
    root.orchestrator.router.calibrators = store
    monkeypatch.setattr(session_attack, "session_views", lambda *_: ({}, "a" * 64))
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "a" * 64)
    for module in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
        version = f"synthetic-{module.value}-views"
        artifact = fit(
            CalibFit(
                scores=[0.1, 0.9] * 8,
                labels=[0, 1] * 8,
                subject_ids=[f"g{i // 2}" for i in range(16)],
                dataset="synthetic-integration-only",
            ),
            module=module,
            model_version=version + "+session-video-v1",
            commit="synthetic",
            n_splits=3,
        )
        store.save(artifact)
        backend = SimpleNamespace(name=module, frames_version=version)
        backend.predict_frames = lambda *_, m=module, v=version: ModuleResult(
            module=m, model_version=v, status="ok", score=0.1, latency_ms=0
        )
        root.orchestrator._detectors[module] = SessionAttackDetector(
            backend, SimpleNamespace(), store
        )
    for module in (Module.GAZE_TRACKING, Module.HEAD_TURN):
        root.orchestrator._detectors[module] = SimpleNamespace(
            predict=lambda *_, m=module: ModuleResult(
                module=m,
                model_version="synthetic-motion",
                status=motion_status,
                gate="pass",
                latency_ms=0,
            )
        )
    created, auth = create(client)
    assert submit_face(client, created, auth)["status"] == expected
