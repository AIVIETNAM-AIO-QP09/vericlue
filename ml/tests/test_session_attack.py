"""A different sampling protocol cannot silently reuse a legacy attack calibrator."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.calibration import CalibFit, CalibrationStore, fit, identity
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Gate, ModuleResult, Status
from vericlue_ml.face import session_attack
from vericlue_ml.face.session_attack import SessionAttackDetector


def attack_input(**kwargs):
    return DetectorInput(
        session_id="ses_attack",
        metadata={
            "challenge_id": "ch_attack",
            "expected_challenge": {
                "challenge_id": "ch_attack",
                "dynamic": {
                    "version": 1,
                    "session_id": "ses_attack",
                    "head_start_at_ms": 12000,
                    "head_duration_ms": 6000,
                },
            },
        },
        **kwargs,
    )


@pytest.mark.parametrize("module", ["face_pad", "face_deepfake"])
def test_session_view_scores_stay_raw_and_use_exact_selected_arrays(monkeypatch, module):
    frames = {
        role: np.full((112, 112, 3), i * 30, np.uint8)
        for i, role in enumerate(("front", "left", "right"), 1)
    }

    class Backend:
        name = module
        frames_version = "synthetic-3views"

        def predict_frames(self, inp, actual):
            assert actual is frames
            return ModuleResult(
                module=module,
                model_version=self.frames_version,
                status="ok",
                score=0.2,
                prob_attack=0.01,
                gate="pass",
                latency_ms=1,
            )

    monkeypatch.setattr(session_attack, "session_views", lambda *_: (frames, "a" * 64))
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "a" * 64)
    result = SessionAttackDetector(Backend(), SimpleNamespace()).predict(
        attack_input(video=Path("server-video.mp4"), images=[Path("not-opened.png")])
    )
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR
    assert result.score == 0.2 and result.prob_attack is None
    assert result.model_version.endswith("+session-video-v1")


def test_changed_video_discards_attack_measurement(monkeypatch):
    backend = SimpleNamespace(
        name="face_pad",
        frames_version="fake",
        predict_frames=lambda *_: ModuleResult(
            module="face_pad", model_version="fake", status="ok", score=0.2, latency_ms=0
        ),
    )
    monkeypatch.setattr(session_attack, "session_views", lambda *_: ({}, "a" * 64))
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "b" * 64)
    result = SessionAttackDetector(backend, SimpleNamespace()).predict(
        attack_input(video=Path("fake.mp4"))
    )
    assert result.status == Status.ERROR and result.score is None
    assert result.error_code == "E_INTEGRITY"


def fixture_detector(monkeypatch, tmp_path, *, status="ok", score=0.2, error=None):
    backend = SimpleNamespace(
        name="face_pad",
        frames_version="synthetic-3views",
        predict_frames=lambda *_: ModuleResult(
            module="face_pad",
            model_version="synthetic-3views",
            status=status,
            score=score,
            error_code=error,
            prob_attack=0.01,
            gate="pass",
            latency_ms=0,
        ),
    )
    monkeypatch.setattr(session_attack, "session_views", lambda *_: ({}, "a" * 64))
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "a" * 64)
    store = CalibrationStore(tmp_path)
    artifact = fit(
        CalibFit(
            scores=[0.1, 0.9] * 8,
            labels=[0, 1] * 8,
            subject_ids=[f"group-{i // 2}" for i in range(16)],
            dataset="synthetic-unit-only",
        ),
        module="face_pad",
        model_version="synthetic-3views+session-video-v1",
        commit="synthetic",
        n_splits=3,
    )
    return backend, store, artifact


def test_valid_fitted_session_artifact_calibrates_raw_score_not_backend_probability(
    monkeypatch, tmp_path
):
    backend, store, artifact = fixture_detector(monkeypatch, tmp_path)
    store.save(artifact)
    result = SessionAttackDetector(backend, SimpleNamespace(), calibrators=store).predict(
        attack_input(video=Path("sample.mp4"))
    )
    assert result.status == Status.OK
    assert result.score == 0.2
    assert result.prob_attack == pytest.approx(artifact.predict([0.2])[0])
    assert result.gate == Gate.UNCLEAR
    assert result.quality["calibrated"] is True
    assert result.quality["depth_verified"] is False


@pytest.mark.parametrize(
    "kind", ["missing", "identity", "provisional", "wrong-version", "wrong-module"]
)
def test_unusable_artifact_never_produces_a_probability(monkeypatch, tmp_path, kind):
    backend, store, artifact = fixture_detector(monkeypatch, tmp_path)
    if kind == "identity":
        store.save(
            identity(module="face_pad", model_version=artifact.model_version, commit="synthetic")
        )
    elif kind == "provisional":
        store.save(artifact.model_copy(update={"provisional": True}))
    elif kind.startswith("wrong"):
        bad = artifact.model_copy(
            update={"model_version": "legacy"}
            if kind == "wrong-version"
            else {"module": "face_deepfake"}
        )
        target = store.path(artifact.module, artifact.model_version)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(bad.model_dump_json(), encoding="utf-8")
    result = SessionAttackDetector(backend, SimpleNamespace(), calibrators=store).predict(
        attack_input(video=Path("sample.mp4"))
    )
    assert result.status == Status.DEGRADED and result.prob_attack is None
    assert result.gate == Gate.UNCLEAR


@pytest.mark.parametrize(
    "status,score,error",
    [
        ("error", 0.2, "E_INTERNAL"),
        ("degraded", 0.2, None),
        ("not_applicable", None, "E_NO_FACE"),
        ("ok", None, None),
        ("ok", float("nan"), None),
        ("ok", 1.2, None),
        ("ok", 0.2, "E_INTERNAL"),
    ],
)
def test_artifact_never_repairs_unusable_backend_measurement(
    monkeypatch, tmp_path, status, score, error
):
    backend, store, artifact = fixture_detector(
        monkeypatch, tmp_path, status=status, score=score, error=error
    )
    store.save(artifact)
    result = SessionAttackDetector(backend, SimpleNamespace(), calibrators=store).predict(
        attack_input(video=Path("sample.mp4"))
    )
    assert result.status != Status.OK and result.prob_attack is None


def test_missing_artifact_is_not_activated_mid_process(monkeypatch, tmp_path):
    backend, store, artifact = fixture_detector(monkeypatch, tmp_path)
    detector = SessionAttackDetector(backend, SimpleNamespace(), calibrators=store)
    assert detector.predict(attack_input(video=Path("sample.mp4"))).prob_attack is None
    store.save(artifact)
    assert detector.predict(attack_input(video=Path("sample.mp4"))).prob_attack is None


@pytest.mark.parametrize("field,value", [("module", "face_deepfake"), ("model_version", "legacy")])
def test_backend_identity_mismatch_is_an_integrity_error(monkeypatch, tmp_path, field, value):
    backend, store, artifact = fixture_detector(monkeypatch, tmp_path)
    store.save(artifact)
    result = backend.predict_frames(None, {})
    backend.predict_frames = lambda *_: result.model_copy(update={field: value})
    measured = SessionAttackDetector(backend, SimpleNamespace(), calibrators=store).predict(
        attack_input(video=Path("sample.mp4"))
    )
    assert measured.status == Status.ERROR and measured.error_code == "E_INTEGRITY"
    assert measured.module == "face_pad" and measured.prob_attack is None


def test_reauth_uses_frontal_frame_and_requires_fitted_calibrator_in_standard_mode(
    monkeypatch, tmp_path
):
    frame = np.full((112, 112, 3), 64, np.uint8)
    backend = SimpleNamespace(
        name="face_deepfake",
        frames_version="gend+3views",
        predict_frame=lambda inp, bgr: ModuleResult(
            module="face_deepfake",
            model_version="gend+single-frame-v1",
            status="ok",
            score=0.15,
            latency_ms=1,
        ),
    )
    reader = SimpleNamespace(
        observe=lambda bgr, at_ms: SimpleNamespace(
            face_count=1, yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0
        )
    )
    monkeypatch.setattr(
        session_attack,
        "select_frontal_frame",
        lambda video, target: SimpleNamespace(bgr=frame, at_ms=500),
    )
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "c" * 64)
    store = CalibrationStore(tmp_path)
    inp = DetectorInput(
        session_id="ses_reauth",
        video=Path("reauth.mp4"),
        metadata={"purpose": "reauth", "challenge_id": "ch_reauth"},
    )
    uncalibrated = SessionAttackDetector(backend, reader, calibrators=store).predict(inp)
    assert uncalibrated.status == Status.DEGRADED
    assert uncalibrated.prob_attack is None
    assert uncalibrated.model_version == "gend+single-frame-v1"

    artifact = fit(
        CalibFit(
            scores=[0.1, 0.9] * 8,
            labels=[0, 1] * 8,
            subject_ids=[f"group-{i // 2}" for i in range(16)],
            dataset="synthetic-unit-only",
        ),
        module="face_deepfake",
        model_version="gend+single-frame-v1",
        commit="synthetic",
        n_splits=3,
    )
    store.save(artifact)
    calibrated = SessionAttackDetector(backend, reader, calibrators=store).predict(inp)
    assert calibrated.status == Status.OK
    assert calibrated.prob_attack == pytest.approx(artifact.predict([0.15])[0])
    assert calibrated.quality["calibrated"] is True
    assert "manual_demo" not in calibrated.quality
