"""Each voice attempt measures its own clip, never the earlier face or retry clip."""

import pytest
from fastapi.testclient import TestClient
from synthetic_images import synthetic_image

from vericlue_api.core.config import get_settings
from vericlue_api.main import create_app
from vericlue_api.services import orchestrator as orchestration
from vericlue_ml.common.result import ErrorCode, Gate, Module, Status
from vericlue_ml.mock.detectors import MockDetector


@pytest.fixture
def voice_client(monkeypatch):
    monkeypatch.setenv("ROUTER_PROFILE", "mvp")
    captured = []

    class CaptureVoice(MockDetector):
        def predict(self, inp):
            result = super().predict(inp)
            if self.name == Module.FACE_DEEPFAKE:
                return result.model_copy(update={"score": 0.45, "prob_attack": 0.45})
            if (
                self.name == Module.VOICE_CHALLENGE
                and inp.audio is not None
                and inp.audio.read_bytes() == b"wrong-phrase"
            ):
                return result.model_copy(update={"gate": Gate.FAIL})
            if self.name == Module.LIPSYNC and inp.session_id is not None:
                captured.append(
                    {
                        "video": inp.video,
                        "bytes": inp.video.read_bytes() if inp.video is not None else None,
                        "prompt": inp.metadata["prompt"],
                    }
                )
                if inp.video is None:
                    return result.model_copy(
                        update={
                            "status": Status.NOT_APPLICABLE,
                            "score": None,
                            "prob_attack": None,
                            "error_code": ErrorCode.E_LOW_QUALITY,
                        }
                    )
            return result

    monkeypatch.setattr(
        orchestration, "get_detector", lambda module, *, mock=None: CaptureVoice(module)
    )
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        captured.clear()
        yield client, captured


def face_then_challenge(client):
    created = client.post("/v1/sessions").json()
    sid = created["session_id"]
    headers = {"Authorization": "Bearer " + created["token"]}
    uploaded = client.post(
        f"/v1/sessions/{sid}/media",
        headers=headers,
        files={
            "image": ("face.jpg", synthetic_image(b"synthetic image"), "image/jpeg"),
            "video": ("face.mp4", b"earlier face clip", "video/mp4"),
        },
    )
    assert uploaded.status_code == 200
    finalized = client.post(f"/v1/sessions/{sid}/finalize", headers=headers)
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "voice_challenge"
    return sid, headers, finalized.json()["voice_prompt"]


@pytest.mark.parametrize("with_voice_video", [False, True])
def test_voice_uses_current_uploaded_clip_or_none_and_preserves_face_clip(
    voice_client, with_voice_video
):
    client, captured = voice_client
    sid, headers, prompt = face_then_challenge(client)
    files = {"audio": ("voice.wav", b"correct phrase", "audio/wav")}
    if with_voice_video:
        files["video"] = ("voice.mp4", b"current speaking clip", "video/mp4")
    response = client.post(f"/v1/sessions/{sid}/voice", headers=headers, files=files)
    assert response.status_code == 200
    assert response.json() == {"status": "pass"}
    assert len(captured) == 1
    assert captured[0]["prompt"] == prompt
    assert captured[0]["bytes"] == (b"current speaking clip" if with_voice_video else None)
    with client.app.state.vericlue.transaction() as state:
        face_video = state.sessions.get(sid).video
        assert face_video.read_bytes() == b"earlier face clip"
        assert captured[0]["video"] != face_video


def test_voice_retry_omitting_video_does_not_reuse_previous_attempt_clip(voice_client):
    client, captured = voice_client
    sid, headers, first_prompt = face_then_challenge(client)
    first = client.post(
        f"/v1/sessions/{sid}/voice",
        headers=headers,
        files={
            "audio": ("voice.wav", b"wrong-phrase", "audio/wav"),
            "video": ("voice.mp4", b"previous attempt clip", "video/mp4"),
        },
    )
    assert first.status_code == 200
    assert first.json()["status"] == "voice_challenge"
    assert first.json()["voice_prompt"] != first_prompt
    assert captured[0]["bytes"] == b"previous attempt clip"
    second = client.post(
        f"/v1/sessions/{sid}/voice",
        headers=headers,
        files={"audio": ("voice.wav", b"correct phrase", "audio/wav")},
    )
    assert second.status_code == 200
    assert second.json() == {"status": "pass"}
    assert len(captured) == 2
    assert captured[1]["video"] is captured[1]["bytes"] is None
    assert captured[1]["prompt"] == first.json()["voice_prompt"]
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).video.read_bytes() == b"earlier face clip"
