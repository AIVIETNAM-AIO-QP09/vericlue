"""MVP tracked artifacts must match actual detector versions without loading weights."""

from __future__ import annotations

from pathlib import Path

import pytest

from vericlue_ml.common.calibration import CalibrationStore, IdentityCalibrator
from vericlue_ml.common.result import Gate, Module, ModuleResult
from vericlue_ml.face import gend, pad
from vericlue_ml.router.policy import TrustRouter
from vericlue_ml.voice.antispoof import AntiDeepfakeDetector

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def repository_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use repository configuration rather than developer overrides; no weights are read."""
    monkeypatch.delenv("CALIBRATORS_DIR", raising=False)
    monkeypatch.delenv("ML_MODELS_CONFIG", raising=False)
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(ROOT / "models" / "manifest.yaml"))


def test_tracked_voice_identity_matches_actual_detector_version() -> None:
    artifact = CalibrationStore().load("voice_spoof", AntiDeepfakeDetector().version)
    assert isinstance(artifact, IdentityCalibrator)
    assert artifact.method == "identity"
    assert artifact.provisional is True
    assert artifact.n_pos == artifact.n_neg == 0
    assert artifact.note == "MVP — không dùng cho báo cáo"


def test_tracked_pad_identity_matches_manifest_revision_version() -> None:
    pad_revision = pad._manifest_entry(pad.PAD_MODEL_ID, pad.PAD_FILE)["revision"]
    detector_revision = pad._manifest_entry(pad.DETECTOR_MODEL_ID, pad.DETECTOR_FILE)["revision"]
    version = f"minifasnet-v2@{pad_revision[:8]}+scrfd-10g@{detector_revision[:8]}"
    artifact = CalibrationStore().load("face_pad", version)
    assert isinstance(artifact, IdentityCalibrator)
    assert artifact.method == "identity"
    assert artifact.provisional is True
    assert artifact.n_pos == artifact.n_neg == 0
    assert artifact.note == "MVP — không dùng cho báo cáo"


@pytest.mark.parametrize(("score", "expected"), [(0.1, "pass"), (0.2, "review")])
def test_mvp_voice_gate_uses_tracked_identity_at_current_threshold(score, expected) -> None:
    router = TrustRouter(profile="mvp")
    assert router.config.voice.spoof_threshold == 0.15
    decision = router.voice(
        {
            Module.VOICE_CHALLENGE: ModuleResult(
                module=Module.VOICE_CHALLENGE,
                model_version="mock@voice-challenge",
                status="ok",
                gate=Gate.PASS,
                latency_ms=1,
            ),
            Module.VOICE_SPOOF: ModuleResult(
                module=Module.VOICE_SPOOF,
                model_version=AntiDeepfakeDetector().version,
                status="ok",
                score=score,
                prob_attack=None,
                latency_ms=1,
            ),
            Module.LIPSYNC: ModuleResult(
                module=Module.LIPSYNC,
                model_version="mock@lipsync",
                status="ok",
                prob_attack=0.01,
                latency_ms=1,
            ),
        }
    )
    assert decision.status == expected
    assert decision.results[Module.VOICE_SPOOF].prob_attack == score


def test_tracked_lipsync_identity_matches_runtime_detector_version() -> None:
    from vericlue_ml.voice.syncnet import SyncNetDetector

    detector = SyncNetDetector()
    artifact = CalibrationStore().load("lipsync", detector.version)
    assert isinstance(artifact, IdentityCalibrator)
    assert artifact.method == "identity"
    assert artifact.provisional is True
    assert artifact.n_pos == artifact.n_neg == 0
    assert artifact.note == "MVP — không dùng cho báo cáo"


def test_tracked_gend_identity_matches_actual_preload_version_without_weights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revisions = {
        "gend": pad._manifest_entry(gend.GEND_MODEL_ID, gend.GEND_WEIGHTS)["revision"],
        "clip": pad._manifest_entry(gend.CLIP_MODEL_ID, gend.CLIP_CONFIG)["revision"],
        "scrfd": pad._manifest_entry(pad.DETECTOR_MODEL_ID, pad.DETECTOR_FILE)["revision"],
    }
    root = tmp_path / "models-without-weights"
    session, classifier, finder = object(), object(), object()
    calls = []

    def shared_scrfd(models_root, device=None):
        assert models_root == root and device == "cpu"
        calls.append("scrfd")
        return session, revisions["scrfd"]

    def load_classifier(models_root, device):
        assert models_root == root and device == "cpu"
        calls.append("classifier")
        return classifier, revisions["gend"], revisions["clip"]

    def face_finder(onnx_session, *, scale, swap_rb):
        assert onnx_session is session
        assert scale == gend.SCRFD_SCALE and swap_rb is True
        calls.append("finder")
        return finder

    monkeypatch.setattr(gend, "shared_scrfd_session", shared_scrfd)
    monkeypatch.setattr(gend, "_load_classifier", load_classifier)
    monkeypatch.setattr(gend, "ScrfdFaceFinder", face_finder)
    detector = gend.FaceDeepfakeDetector(models_dir=root)
    initial_version = detector.version
    detector.preload(models_dir=root, device="cpu")
    detector.preload(models_dir=root, device="cpu")
    assert calls == ["scrfd", "classifier", "finder"]
    assert detector.version != initial_version
    assert detector.version.split("+") == [
        f"gend-clip-l14@{revisions['gend'][:8]}",
        f"clip@{revisions['clip'][:8]}",
        f"scrfd-10g@{revisions['scrfd'][:8]}",
        "agg-maxmeantop25-v1",
    ]
    artifact = CalibrationStore().load("face_deepfake", detector.version)
    assert isinstance(artifact, IdentityCalibrator)
    assert artifact.method == "identity"
    assert artifact.provisional is True
    assert artifact.n_pos == artifact.n_neg == 0
    assert artifact.note == "MVP — không dùng cho báo cáo"
