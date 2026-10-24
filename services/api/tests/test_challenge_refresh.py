"""LIVE-06: POST /challenge cấp gói mới (cả gói LIVE-01 `dynamic`) và token mới, trong giới hạn tổng (ADR-0017)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import start_session
from contract_utils import validate

CHALLENGE = "/v1/sessions/{sid}/challenge"


def test_refresh_gives_a_new_challenge_and_a_new_token(client):
    body, auth = start_session(client)
    sid = body["session_id"]
    res = client.post(CHALLENGE.format(sid=sid), headers=auth)
    assert res.status_code == 200, res.text
    out = res.json()
    validate(out, "session", "ChallengeResponse")
    assert out["challenge"]["challenge_id"] != body["challenge"]["challenge_id"]
    assert out["expires_at"] >= body["expires_at"]
    assert out["token"] != body["token"]
    # Token cũ hết hiệu lực; token mới dùng được.
    assert client.post(CHALLENGE.format(sid=sid), headers=auth).status_code == 401
    new = {"Authorization": f"Bearer {out['token']}"}
    assert client.post(CHALLENGE.format(sid=sid), headers=new).status_code == 200


def test_refresh_is_refused_after_the_session_limit(client):
    body, auth = start_session(client)
    sid = body["session_id"]
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).created_at = datetime.now(UTC) - timedelta(minutes=16)
    res = client.post(CHALLENGE.format(sid=sid), headers=auth)
    assert res.status_code == 409
    assert res.json()["error_code"] == "session_too_long"


def test_refresh_never_extends_past_the_session_limit(client):
    body, auth = start_session(client)
    sid = body["session_id"]
    started = datetime.now(UTC) - timedelta(minutes=14)
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).created_at = started
    out = client.post(CHALLENGE.format(sid=sid), headers=auth).json()
    expires = datetime.fromisoformat(out["expires_at"].replace("Z", "+00:00"))
    assert expires <= started + timedelta(minutes=15, seconds=1)


def test_refresh_drops_the_old_face_attempt(client):
    body, auth = start_session(client)
    sid = body["session_id"]
    with client.app.state.vericlue.transaction() as state:
        s = state.sessions.get(sid)
        s.signals = {"color_events": [1]}
        s.voice_requested = True
    client.post(CHALLENGE.format(sid=sid), headers=auth)
    with client.app.state.vericlue.transaction() as state:
        s = state.sessions.get(sid)
        assert s.signals == {} and s.voice_requested is False


FINALIZE = "/v1/sessions/{sid}/finalize"
VOICE = "/v1/sessions/{sid}/voice"
AUDIO = {"audio": ("voice.wav", b"synthetic audio", "audio/wav")}


def _refresh(client, sid, auth) -> dict:
    """POST /challenge; trả header Bearer với token MỚI (token cũ hết hiệu lực)."""
    res = client.post(CHALLENGE.format(sid=sid), headers=auth)
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def test_refresh_does_not_escape_the_voice_step(client):
    """Đã bị đòi đọc câu thì lượt mặt mới (dù ra pass) vẫn phải đọc câu."""
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "voice_challenge"
    auth = _refresh(client, sid, auth)
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).scenario = "genuine"  # lượt mặt mới tự nó sẽ ra pass
    again = client.post(FINALIZE.format(sid=sid), headers=auth).json()
    assert again["status"] == "voice_challenge"


def test_refresh_after_a_scored_attempt_uses_up_a_retry(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    client.post(FINALIZE.format(sid=sid), headers=auth)
    for _ in range(3):
        auth = _refresh(client, sid, auth)
        client.post(FINALIZE.format(sid=sid), headers=auth)
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).retries_used >= 3


def test_refresh_after_a_retry_is_not_counted_twice(client):
    body, auth = start_session(client, "low_quality")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "retry"
    client.post(CHALLENGE.format(sid=sid), headers=auth)
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).retries_used == 1


def test_refresh_drops_old_results(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    client.post(FINALIZE.format(sid=sid), headers=auth)
    client.post(CHALLENGE.format(sid=sid), headers=auth)
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).results == {}


def test_voice_done_clears_what_is_owed(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "voice_challenge"
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).voice_owed is True
        state.sessions.get(sid).scenario = "genuine"  # giọng đọc lần này ra pass
    assert client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO).json()["status"] == "pass"
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).voice_owed is False


def test_refresh_of_a_purpose_session_renews_the_dynamic_pack(client):
    res = client.post(
        "/v1/sessions",
        headers={"X-Mock-Scenario": "genuine"},
        json={"purpose": "onboarding", "nonce": "integration_nonce_12345678"},
    )
    body = res.json()
    sid, auth = body["session_id"], {"Authorization": f"Bearer {body['token']}"}
    old = body["challenge"]["dynamic"]
    out = client.post(CHALLENGE.format(sid=sid), headers=auth).json()
    new = out["challenge"]["dynamic"]
    assert new["voice_challenge_id"] != old["voice_challenge_id"]
    assert new["gaze_points"] != old["gaze_points"]
    assert out["challenge"]["challenge_id"] != body["challenge"]["challenge_id"]
