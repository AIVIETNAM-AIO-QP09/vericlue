"""Real API scheduler/privacy, synthetic biometric verdicts; no weights/camera."""

import base64
import secrets
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_accounts import prepared

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import utcnow
from vericlue_api.main import create_app
from vericlue_api.services import orchestrator as orchestration
from vericlue_api.services.uploads import save_upload
from vericlue_ml.common.result import Evidence, Module, ModuleResult
from vericlue_ml.face.continuity import FACE_VOICE_VERSION, FaceContinuityDetector
from vericlue_ml.face.video_match import VideoFaceMatchDetector


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("IDENTITY_CARD_ENABLED", "true")
    monkeypatch.setenv("IDENTITY_FACE_FROM_VIDEO", "true")
    monkeypatch.setenv("IDENTITY_VOICE_CONTINUITY", "true")
    instances, inputs = [], []

    class Reader:
        def preload(self, **kwargs):
            pass

        def close(self):
            pass

    class Matcher(VideoFaceMatchDetector):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            instances.append(self)

        def preload(self, **kwargs):
            pass

    def predict(model, inp):
        inputs.append(inp)
        assert inp.reference_video.read_bytes() == b"synthetic-face-video"
        assert inp.video.read_bytes() == b"synthetic-voice-video"
        assert inp.audio.read_bytes() == b"synthetic-audio"
        assert inp.metadata["expected_voice_challenge_id"] == inp.metadata["voice_challenge_id"]
        return ModuleResult(
            module=Module.FACE_CONTINUITY,
            model_version=FACE_VOICE_VERSION,
            status="ok",
            gate="pass",
            latency_ms=0,
            evidence=[
                Evidence(type="text", name=name, value=value)
                for name, value in {
                    "source_video_sha256": "c" * 64,
                    "voice_challenge_id": inp.metadata["voice_challenge_id"],
                    "challenge_id": inp.metadata["challenge_id"],
                }.items()
            ],
        )

    monkeypatch.setattr(orchestration, "FaceObservationReader", Reader)
    monkeypatch.setattr(orchestration, "VideoFaceMatchDetector", Matcher)
    monkeypatch.setattr(FaceContinuityDetector, "predict", predict)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client, inputs, instances


def ready(state):
    session, _, _ = prepared(state)
    session.completed = False
    session.voice_requested = session.voice_owed = True
    session.voice_expires_at = utcnow() + timedelta(seconds=120)
    session.accepted_steps.remove("voice")
    folder = state.settings.media_dir
    session.video = save_upload(
        folder,
        session.session_id,
        "face_video",
        "face.mp4",
        b"synthetic-face-video",
        privacy=state.privacy,
    )
    session.audio = save_upload(
        folder,
        session.session_id,
        "voice_audio",
        "speech.wav",
        b"synthetic-audio",
        privacy=state.privacy,
    )
    voice = save_upload(
        folder,
        session.session_id,
        "voice_video",
        "speech.mp4",
        b"synthetic-voice-video",
        privacy=state.privacy,
    )
    return session, voice


@pytest.mark.parametrize(
    "fault", ["none", "degraded", "error", "unclear", "version", "voice", "source"]
)
def test_voice_runs_continuity_with_decrypted_bound_sources_and_never_overrides_other_gates(
    enabled, monkeypatch, fault
):
    client, inputs, instances = enabled
    root = client.app.state.vericlue
    original = FaceContinuityDetector.predict

    def result(model, inp):
        value = original(model, inp)
        if fault in {"degraded", "error"}:
            value.status = fault
        elif fault == "unclear":
            value.gate = "unclear"
        elif fault == "version":
            value.model_version = "mock@" + FACE_VOICE_VERSION
        elif fault in {"voice", "source"}:
            value.evidence[1 if fault == "voice" else 0].value = "wrong-context"
        return value

    monkeypatch.setattr(FaceContinuityDetector, "predict", result)
    with root.transaction() as state:
        session, voice = ready(state)
        expected_face = session.results[Module.FACE_MATCH].model_copy(deep=True)
        sid = session.session_id
        outcome = state.flow.voice(session, voice_video=voice, audio_offset_ms=600)
        assert outcome.status == ("pass" if fault == "none" else "review")
        assert session.results[Module.FACE_MATCH] == expected_face
        assert not any(
            word in outcome.model_dump_json() for word in ("score", "embedding", "cosine")
        )
        assert inputs[-1].metadata["audio_offset_ms"] == 600
        assert inputs[-1].reference_video != session.video
        assert not inputs[-1].reference_video.exists()  # Lease closed after native work finished.
    assert len(instances) == 1
    assert root.orchestrator.loaded_detector(Module.FACE_CONTINUITY).matcher is instances[0]
    with root.transaction() as state:
        saved = state.sessions.get(sid)
        assert saved.voice_video == voice and isinstance(saved.voice_video, Path)
        assert saved.voice_audio_offset_ms == 600


def test_continuity_opt_in_requires_signed_media_before_writing_files(enabled):
    client, _, _ = enabled
    root = client.app.state.vericlue
    with root.transaction() as state:
        session, _ = ready(state)
        with pytest.raises(ApiError):
            state.flow.accept_voice_media(session, audio=b"not signed", audio_filename="a.wav")
        assert session.audio.read_bytes() != b"not signed"


def test_new_voice_prompt_clears_previous_identity_result_and_video(enabled):
    client, _, _ = enabled
    with client.app.state.vericlue.transaction() as state:
        session, voice = ready(state)
        session.voice_video = voice
        session.voice_audio_offset_ms = 600
        session.results[Module.FACE_CONTINUITY] = ModuleResult(
            module=Module.FACE_CONTINUITY,
            model_version=FACE_VOICE_VERSION,
            status="ok",
            gate="pass",
            latency_ms=0,
        )
        old = session.voice_challenge_id
        state.flow._new_prompt(session)
        assert session.voice_challenge_id != old
        assert Module.FACE_CONTINUITY not in session.results
        assert session.voice_video is session.voice_audio_offset_ms is None


def test_continuity_settings_require_existing_video_identity():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(identity_voice_continuity=True, identity_face_from_video=False)
