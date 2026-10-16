"""Các lỗ hổng reviewer tìm ra ở PLAT-04: đường tắt /voice, token lạ, upload quá lớn, bảng màu xấu."""

from __future__ import annotations

import random

import pytest
from conftest import start_session
from fastapi.testclient import TestClient

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.main import create_app
from vericlue_api.services.challenge import generate_challenge

AUDIO = {"audio": ("voice.wav", b"RIFF", "audio/wav")}
IMAGE = {"image": ("face.jpg", b"\xff\xd8\xff", "image/jpeg")}
FINALIZE = "/v1/sessions/{sid}/finalize"
VOICE = "/v1/sessions/{sid}/voice"


@pytest.mark.parametrize("scenario", ["print", "replay", "faceswap", "virtual_cam", "genuine"])
def test_voice_without_voice_challenge_cannot_pass(client, scenario):
    """Gọi thẳng /voice, bỏ qua quality/hiện diện/khuôn mặt, không được ra 'pass'."""
    body, auth = start_session(client, scenario)
    res = client.post(VOICE.format(sid=body["session_id"]), headers=auth, files=AUDIO)
    assert res.status_code == 409
    assert res.json()["error_code"] == "voice_not_requested"


def test_voice_after_finalize_pass_is_not_requested(client):
    body, auth = start_session(client, "genuine")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json() == {"status": "pass"}
    assert client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO).status_code == 409


def test_voice_step_is_single_use_after_it_finishes(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "voice_challenge"
    assert client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO).json() == {
        "status": "review"
    }
    assert client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO).status_code == 409


def test_genuine_voice_passes_once_requested(client):
    body, auth = start_session(client, "genuine")
    sid = body["session_id"]
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).voice_requested = True
    assert client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO).json() == {
        "status": "pass"
    }


@pytest.mark.parametrize("token", ["café", "mật-khẩu", "ÿþ"])
def test_non_ascii_bearer_is_401_not_500(client, token):
    body, _ = start_session(client)
    headers = {"Authorization": f"Bearer {token}".encode("latin-1", errors="ignore")}
    res = client.post(FINALIZE.format(sid=body["session_id"]), headers=headers)
    assert res.status_code == 401


def test_final_decision_can_only_be_recorded_once(client):
    case_id = client.get("/v1/review/cases").json()["items"][0]["case_id"]
    client.post(f"/v1/review/cases/{case_id}/initial", json={"decision": "accept"})
    final = {"decision": "accept", "reason_code": "OK"}
    assert client.post(f"/v1/review/cases/{case_id}/decision", json=final).status_code == 200
    again = client.post(f"/v1/review/cases/{case_id}/decision", json=final)
    assert again.status_code == 409 and again.json()["error_code"] == "decision_already_recorded"


def test_oversized_upload_is_rejected_with_413(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    client = TestClient(create_app())
    body, auth = start_session(client)
    big = {"image": ("face.jpg", b"0" * (1024 * 1024 + 1), "image/jpeg")}
    res = client.post(f"/v1/sessions/{body['session_id']}/media", headers=auth, files=big)
    assert res.status_code == 413 and res.json()["error_code"] == "upload_too_large"
    ok = client.post(f"/v1/sessions/{body['session_id']}/media", headers=auth, files=IMAGE)
    assert ok.status_code == 200


@pytest.mark.parametrize(
    "palette",
    [
        "#000000,#ffffff",  # chênh độ chói quá lớn
        "#ffcc73,#ff0000",  # chênh độ chói lớn và đỏ bão hòa
        "#ff1010,#ff1111",  # R/(R+G+B) >= 0,8
        "#ffcc73",  # chỉ 1 màu
    ],
)
def test_unsafe_configured_palette_is_rejected(palette):
    with pytest.raises(ValueError):
        generate_challenge(Settings(challenge_palette=palette), rng=random.Random(0))


def test_safe_configured_palette_is_accepted():
    ch = generate_challenge(Settings(challenge_palette="#ffcc73,#73d9ff"), rng=random.Random(0))
    assert {s.rgb for s in ch.color_sequence} <= {"#ffcc73", "#73d9ff"}


# --- Vòng 2: thứ tự luồng (không phải máy trạng thái PLAT-06) ---


def _session(client, sid):
    with client.app.state.vericlue.transaction() as state:
        return state.sessions.get(sid)


def test_finalize_resets_voice_request_so_a_review_blocks_voice(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "voice_challenge"
    assert _session(client, sid).voice_requested is True

    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).scenario = "print"  # lần finalize sau ra review
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json() == {"status": "review"}
    assert _session(client, sid).voice_requested is False
    res = client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO)
    assert res.status_code == 409


def test_review_is_final_finalize_and_voice_return_409_never_pass(client):
    body, auth = start_session(client, "print")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json() == {"status": "review"}

    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).scenario = "genuine"  # kể cả khi dữ liệu sau đó "đẹp"
    for _ in range(2):
        again = client.post(FINALIZE.format(sid=sid), headers=auth)
        assert again.status_code == 409 and again.json()["error_code"] == "session_closed"
    voice = client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO)
    assert voice.status_code == 409 and voice.json()["error_code"] == "session_closed"
    assert (
        len([c for c in client.get("/v1/review/cases").json()["items"] if c["session_id"] == sid])
        == 1
    )


def test_rejected_voice_writes_no_file(client, tmp_path):
    body, auth = start_session(client, "genuine")
    sid = body["session_id"]
    assert client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO).status_code == 409
    assert not (tmp_path / "media" / sid).exists()


def test_unknown_retry_hint_falls_back_to_more_light(client, monkeypatch):
    from vericlue_api.services import session_flow
    from vericlue_api.services.provisional_decision import Outcome

    monkeypatch.setattr(
        session_flow.TrustRouter,
        "finalize",
        lambda *a, **k: Outcome("retry", retry_hint="LẠ_HOẮC_XẤU"),
    )
    body, auth = start_session(client, "genuine")
    res = client.post(FINALIZE.format(sid=body["session_id"]), headers=auth)
    assert res.status_code == 200
    assert res.json()["status"] == "retry" and res.json()["retry_hint"] == "MORE_LIGHT"


def test_new_voice_request_resets_reread_counter(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    _session(client, sid).voice_rereads_used = 1
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "voice_challenge"
    assert _session(client, sid).voice_rereads_used == 0
