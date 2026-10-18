"""ROUT-01 profile isolation through settings, startup and the citizen API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.main import create_app
from vericlue_api.services import orchestrator as orchestration
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_ml.common.result import ErrorCode, Module, ModuleResult, Status
from vericlue_ml.mock.detectors import MockDetector

MVP_MODULES = {
    Module.QUALITY,
    Module.FACE_PAD,
    Module.FACE_DEEPFAKE,
    Module.CAMPROBE,
    Module.VOICE_CHALLENGE,
    Module.VOICE_SPOOF,
    Module.LIPSYNC,
}

VOICE_MODULES = {Module.VOICE_CHALLENGE, Module.VOICE_SPOOF, Module.LIPSYNC}


def test_settings_default_profile_preserves_full(monkeypatch):
    monkeypatch.delenv("ROUTER_PROFILE", raising=False)
    assert Settings(_env_file=None).router_profile == "full"


def test_settings_reads_mvp_profile_from_environment(monkeypatch):
    monkeypatch.setenv("ROUTER_PROFILE", "mvp")
    assert Settings(_env_file=None).router_profile == "mvp"


def test_settings_rejects_unknown_profile():
    with pytest.raises(ValidationError, match="router_profile"):
        Settings(router_profile="unknown", _env_file=None)


@pytest.mark.parametrize("profile", ["full", "mvp"])
def test_only_profile_modules_are_constructed_preloaded_and_run(profile):
    constructed, preloaded, predicted = [], [], []

    class TrackedDetector(MockDetector):
        def preload(self):
            preloaded.append(Module(self.name))

        def predict(self, inp):
            predicted.append(Module(self.name))
            return super().predict(inp)

    def factory(module):
        constructed.append(module)
        return TrackedDetector(module)

    engine = Orchestrator(Settings(router_profile=profile), detector_factory=factory)
    expected = set(Module) if profile == "full" else MVP_MODULES
    try:
        engine.start()
        engine.start()
        assert set(constructed) == expected
        assert len(constructed) == len(expected)
        assert set(preloaded) == expected
        assert len(preloaded) == len(expected)
        results = engine.run(Module, session_id="profile-test", scenario="genuine")
        assert set(results) == set(Module)
        assert set(predicted) == expected
        for module in set(Module) - expected:
            disabled = results[module]
            assert disabled.status == Status.ERROR
            assert disabled.error_code == ErrorCode.E_INTERNAL
            assert disabled.prob_attack is None
            assert any(
                evidence.name == "orchestration_reason"
                and evidence.value == "disabled_by_profile"
                and evidence.label_vi == "Bước này đang tắt ở chế độ MVP"
                for evidence in disabled.evidence
            )
        assert not engine.failed_modules
    finally:
        engine.close()


def test_lipsync_lazy_configuration_receives_configured_model_root_and_device(monkeypatch):
    preloads = []

    class ConfiguredSyncNet(MockDetector):
        def __init__(self):
            super().__init__(Module.LIPSYNC)

        def configure(self, *, models_dir=None, device="cpu"):
            preloads.append((models_dir, device))

    monkeypatch.setattr(orchestration, "SyncNetDetector", ConfiguredSyncNet)
    settings = Settings(
        router_profile="mvp", models_dir="configured-models", device="cuda", lipsync_device="cpu"
    )
    engine = Orchestrator(
        settings,
        detector_factory=lambda module: (
            ConfiguredSyncNet() if module == Module.LIPSYNC else MockDetector(module)
        ),
    )
    try:
        engine.start()
        engine.start()
        assert preloads == [(Path(settings.models_dir), settings.lipsync_device)]
        assert not engine.failed_modules
    finally:
        engine.close()


def test_mvp_mock_citizen_flow_runs_face_then_voice_without_disabled_modules(monkeypatch):
    monkeypatch.setenv("ROUTER_PROFILE", "mvp")
    predicted = []

    class BorderlineFace(MockDetector):
        def predict(self, inp):
            predicted.append(Module(self.name))
            result = super().predict(inp)
            if self.name == Module.FACE_DEEPFAKE:
                return result.model_copy(update={"score": 0.45, "prob_attack": 0.45})
            return result

    monkeypatch.setattr(
        orchestration, "get_detector", lambda module, *, mock=None: BorderlineFace(module)
    )
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        predicted.clear()  # Startup seeds staff demo cases through the same orchestrator.
        created = client.post("/v1/sessions").json()
        sid = created["session_id"]
        headers = {"Authorization": "Bearer " + created["token"]}
        response = client.post(f"/v1/sessions/{sid}/finalize", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "voice_challenge"
        assert set(predicted) == MVP_MODULES - VOICE_MODULES
        predicted.clear()
        response = client.post(
            f"/v1/sessions/{sid}/voice",
            headers=headers,
            files={"audio": ("voice.wav", b"synthetic audio", "audio/wav")},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "pass"}
        assert set(predicted) == VOICE_MODULES
        with client.app.state.vericlue.transaction() as state:
            assert set(state.sessions.get(sid).results) == MVP_MODULES


@pytest.mark.parametrize("module", sorted(MVP_MODULES - {Module.LIPSYNC}, key=str))
@pytest.mark.parametrize("status", [Status.ERROR, Status.DEGRADED, Status.NOT_APPLICABLE])
def test_mvp_required_module_failure_always_reviews(monkeypatch, module, status):
    monkeypatch.setenv("ROUTER_PROFILE", "mvp")

    class FailedDetector(MockDetector):
        def predict(self, inp):
            if self.name == module:
                return ModuleResult(
                    module=module,
                    model_version=self.version,
                    status=status,
                    error_code=ErrorCode.E_INTERNAL,
                    latency_ms=0,
                )
            result = super().predict(inp)
            if module in VOICE_MODULES and self.name == Module.FACE_DEEPFAKE:
                return result.model_copy(update={"score": 0.45, "prob_attack": 0.45})
            return result

    monkeypatch.setattr(
        orchestration, "get_detector", lambda selected, *, mock=None: FailedDetector(selected)
    )
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        created = client.post("/v1/sessions").json()
        sid = created["session_id"]
        headers = {"Authorization": "Bearer " + created["token"]}
        response = client.post(f"/v1/sessions/{sid}/finalize", headers=headers)
        if module in VOICE_MODULES:
            assert response.json()["status"] == "voice_challenge"
            response = client.post(
                f"/v1/sessions/{sid}/voice",
                headers=headers,
                files={"audio": ("voice.wav", b"synthetic audio", "audio/wav")},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "review"}
