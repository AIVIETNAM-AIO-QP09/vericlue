"""`/voice` nhận `audio_offset_ms` (độ lệch WAV so với video, app Android) và chuyển cho mô-đun."""

from __future__ import annotations

import pytest
from conftest import start_session

from vericlue_api.services.orchestrator import Orchestrator

FINALIZE = "/v1/sessions/{sid}/finalize"
VOICE = "/v1/sessions/{sid}/voice"
FILES = {
    "audio": ("voice.wav", b"synthetic audio", "audio/wav"),
    "video": ("voice.mp4", b"synthetic video", "video/mp4"),
}


@pytest.fixture
def seen_metadata(monkeypatch):
    seen: list[dict] = []
    original = Orchestrator.run

    def spy(self, *args, **kwargs):
        seen.append(dict(kwargs.get("extra_metadata") or {}))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Orchestrator, "run", spy)
    return seen


def _voice(client, offset: str | None):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "voice_challenge"
    data = {} if offset is None else {"audio_offset_ms": offset}
    return client.post(VOICE.format(sid=sid), headers=auth, files=FILES, data=data)


def test_offset_reaches_the_voice_modules(client, seen_metadata):
    res = _voice(client, "640")
    assert res.status_code == 200, res.text
    assert seen_metadata[-1]["audio_offset_ms"] == 640


def test_offset_is_optional(client, seen_metadata):
    res = _voice(client, None)
    assert res.status_code == 200, res.text
    assert "audio_offset_ms" not in seen_metadata[-1]


def test_offset_out_of_range_is_422(client):
    assert _voice(client, "60000").status_code == 422
