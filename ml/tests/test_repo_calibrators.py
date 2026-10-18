"""MVP tracked artifacts must match actual detector versions without loading weights."""

from __future__ import annotations

from pathlib import Path

import pytest

from vericlue_ml.common.calibration import CalibrationStore, IdentityCalibrator
from vericlue_ml.common.result import Gate, Module, ModuleResult
from vericlue_ml.face import pad
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
        }
    )
    assert decision.status == expected
    assert decision.results[Module.VOICE_SPOOF].prob_attack == score
