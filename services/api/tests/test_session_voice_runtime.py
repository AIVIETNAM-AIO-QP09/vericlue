"""Opt-in session voice models use compatible workers, with no model/device access."""

from pathlib import Path

from vericlue_api.core.config import Settings
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_ml.common.result import Module
from vericlue_ml.voice.session import SessionVoiceDetector


def test_missing_runtime_is_unavailable_instead_of_mock_pass():
    app = Orchestrator(Settings(use_mock_models=True, session_voice_models=True))
    try:
        app.start()
        assert set(app.failed_modules) == {"voice_challenge", "voice_spoof", "lipsync"}
        results = app.run(
            [Module.VOICE_CHALLENGE, Module.VOICE_SPOOF, Module.LIPSYNC],
            session_id="ses_synthetic",
            scenario="genuine",
        )
        assert all(r.status == "error" and r.gate != "pass" for r in results.values())
    finally:
        app.close()


def test_worker_runtime_is_shared_within_application_only(monkeypatch, tmp_path):
    from vericlue_api.services import orchestrator as module

    class Client:
        def __init__(self, python, models_dir, media_root, *, timeout):
            self.python, self.models_dir = python, models_dir
            self.media_root, self.timeout = media_root, timeout
            self.closed = 0

        def preload(self):
            pass

        def close(self):
            self.closed += 1

    monkeypatch.setattr(module, "VoiceWorkerClient", Client)
    settings = Settings(
        use_mock_models=True,
        router_profile="mvp",
        session_voice_models=True,
        voice_runtime_python="synthetic-qwen-runtime.exe",
        voice_spoof_python="synthetic-nes-runtime.exe",
        media_dir=str(tmp_path),
    )
    first, second = Orchestrator(settings), Orchestrator(settings)
    try:
        first.start()
        second.start()
        content = first.loaded_detector(Module.VOICE_CHALLENGE)
        lipsync = first.loaded_detector(Module.LIPSYNC)
        spoof = first.loaded_detector(Module.VOICE_SPOOF)
        assert all(isinstance(d, SessionVoiceDetector) for d in (content, lipsync, spoof))
        assert content.client is lipsync.client and spoof.client is not content.client
        assert content.client is not second.loaded_detector(Module.VOICE_CHALLENGE).client
        assert content.match_config is settings.router_config.voice
        assert content.client.python == Path("synthetic-qwen-runtime.exe")
        assert spoof.client.python == Path("synthetic-nes-runtime.exe")
        assert not first.failed_modules
        first.close()
        first.close()
        assert content.client.closed == spoof.client.closed == 1
        assert second.loaded_detector(Module.VOICE_CHALLENGE).client.closed == 0
    finally:
        first.close()
        second.close()
