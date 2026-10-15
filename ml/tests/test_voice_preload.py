"""VOICE-04 public preload hooks without GPU, weights, audio or network."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from vericlue_ml.voice.asr import ASRError, PhoWhisperASR
from vericlue_ml.voice.challenge import VoiceChallengeDetector


def test_asr_public_preload_serializes_and_loads_model_once(monkeypatch):
    asr = PhoWhisperASR()
    loads = []

    def fake_load():
        if asr._model is None:
            loads.append("load")
            asr._model = object()

    monkeypatch.setattr(asr, "_load", fake_load)
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(lambda _: asr.preload(), range(8)))
    assert loads == ["load"]
    assert asr._model is not None


def test_voice_challenge_public_preload_delegates_without_inference():
    class FakeASR:
        version = "synthetic@preload"
        calls = 0

        def preload(self):
            self.calls += 1

        def transcribe(self, _path):
            raise AssertionError("preload must not run transcription")

    provider = FakeASR()
    detector = VoiceChallengeDetector(asr=provider)
    detector.preload()
    assert provider.calls == 1
    assert detector.version == provider.version


def test_asr_reads_external_models_config_without_source_checkout(tmp_path, monkeypatch):
    from vericlue_ml.voice import asr as asr_module

    deployed_module = tmp_path / "wheel-env/site-packages/vericlue_ml/voice/asr.py"
    deployed_module.parent.mkdir(parents=True)
    deployed_module.write_text("# installed wheel placeholder", encoding="utf-8")
    monkeypatch.setattr(asr_module, "__file__", str(deployed_module))
    config = tmp_path / "deployment-config/models.yaml"
    config.parent.mkdir()
    revision = "a" * 40
    config.write_text(
        f"voice:\n  model_subdir: custom-phowhisper\n  revision: {revision}\n"
        "  vad_mode: 2\n  cpu_threads: 2\n",
        encoding="utf-8",
    )
    weights = tmp_path / "mounted-weights"
    monkeypatch.setenv("ML_MODELS_CONFIG", str(config))
    monkeypatch.setenv("MODELS_DIR", str(weights))
    provider = asr_module.PhoWhisperASR()
    assert provider.model_dir == weights / "custom-phowhisper"
    assert provider.version == f"phowhisper-small@{revision}+voice04-v1"
    assert provider.vad_mode == 2 and provider.cpu_threads == 2
    assert provider._model is None and provider._processor is None


def test_preload_configured_root_keeps_model_subdir_and_cannot_repoint_loaded_model(
    tmp_path, monkeypatch
):
    config = tmp_path / "models.yaml"
    config.write_text("voice:\n  model_subdir: nested/custom-voice\n", encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_CONFIG", str(config))
    monkeypatch.setenv("MODELS_DIR", str(tmp_path / "initial-env-root"))
    provider = PhoWhisperASR()
    loads = []

    def fake_load():
        if provider._model is None:
            loads.append(provider.model_dir)
            provider._model = object()

    monkeypatch.setattr(provider, "_load", fake_load)
    configured = tmp_path / "mounted-settings-root"
    VoiceChallengeDetector(asr=provider).preload(models_dir=configured)
    assert provider.model_dir == configured.resolve() / "nested/custom-voice"
    provider.preload(models_dir=configured)
    assert loads == [configured.resolve() / "nested/custom-voice"]
    with pytest.raises(ASRError):
        provider.preload(models_dir=tmp_path / "another-root")
    assert provider.model_dir == configured.resolve() / "nested/custom-voice"
    assert len(loads) == 1
