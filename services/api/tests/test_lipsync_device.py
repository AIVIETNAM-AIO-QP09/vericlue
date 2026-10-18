"""Lipsync has an independent device and configures lazily without loading weights."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from vericlue_api.core.config import Settings
from vericlue_api.services import orchestrator as orchestration
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector


def test_lipsync_device_defaults_to_cpu_independently_of_global_device(monkeypatch):
    monkeypatch.delenv("LIPSYNC_DEVICE", raising=False)
    monkeypatch.setenv("DEVICE", "cuda")
    settings = Settings(_env_file=None)
    assert settings.device == "cuda"
    assert settings.lipsync_device == "cpu"


@pytest.mark.parametrize("device", ["cpu", "cuda", "auto"])
def test_lipsync_device_reads_its_own_environment_variable(monkeypatch, device):
    monkeypatch.setenv("DEVICE", "cpu")
    monkeypatch.setenv("LIPSYNC_DEVICE", device)
    settings = Settings(_env_file=None)
    assert settings.device == "cpu"
    assert settings.lipsync_device == device


@pytest.mark.parametrize("device", ["gpu", "cuda:0", "cuda:1", "", "none"])
def test_lipsync_device_rejects_values_outside_cpu_cuda_auto(monkeypatch, device):
    monkeypatch.setenv("LIPSYNC_DEVICE", device)
    with pytest.raises(ValidationError, match="lipsync_device"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "other_module,class_name",
    [
        (Module.FACE_PAD, "FacePadDetector"),
        (Module.FACE_DEEPFAKE, "FaceDeepfakeDetector"),
        (Module.QUALITY, "QualityDetector"),
        (Module.VOICE_CHALLENGE, "VoiceChallengeDetector"),
        (Module.VOICE_SPOOF, "AntiDeepfakeDetector"),
    ],
)
@pytest.mark.parametrize(
    "global_device,lipsync_device",
    [("cuda", "cpu"), ("cpu", "cuda"), ("auto", "cpu"), ("cuda", "auto")],
)
def test_start_configures_lipsync_without_preload_and_preserves_other_model_device(
    monkeypatch, other_module, class_name, global_device, lipsync_device
):
    configured, preloaded = [], []

    class LazySyncNet(MockDetector):
        def __init__(self):
            super().__init__(Module.LIPSYNC)

        def configure(self, *, models_dir=None, device="cpu"):
            configured.append((models_dir, device))

        def preload(self, **kwargs):
            raise AssertionError("Orchestrator startup must not load lipsync/CTC weights")

    class OtherDetector(MockDetector):
        def __init__(self):
            super().__init__(other_module)

        def preload(self, *, models_dir=None, device=None):
            preloaded.append((models_dir, device))

    monkeypatch.setattr(orchestration, "SyncNetDetector", LazySyncNet)
    monkeypatch.setattr(orchestration, class_name, OtherDetector)
    monkeypatch.setenv("MODELS_DIR", "ignored-env-models")
    monkeypatch.setenv("LIPSYNC_DEVICE", "cpu" if lipsync_device != "cpu" else "cuda")
    settings = Settings(
        router_profile="mvp",
        models_dir="configured-models",
        device=global_device,
        lipsync_device=lipsync_device,
        _env_file=None,
    )

    def factory(module):
        if module == Module.LIPSYNC:
            return LazySyncNet()
        if module == other_module:
            return OtherDetector()
        return MockDetector(module)

    engine = Orchestrator(settings, detector_factory=factory)
    try:
        engine.start()
        engine.start()
        assert configured == [(Path(settings.models_dir), lipsync_device)]
        assert preloaded == [(Path(settings.models_dir), global_device)]
        assert not engine.failed_modules
        assert Module.LIPSYNC in engine._detectors
    finally:
        engine.close()
