"""LIVE-01: gói thử thách có thứ tự quay đầu và đường chấm sáng; cấp thử thách mới và gia hạn (ADR-0017)."""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

import pytest
from conftest import start_session
from contract_utils import validate

from vericlue_api.core.config import Settings
from vericlue_api.services.challenge import (
    DOT_MARGIN,
    DOT_MIN_JUMP,
    DOT_POINTS,
    DOT_STEP_MS,
    generate_challenge,
)

CHALLENGE = "/v1/sessions/{sid}/challenge"


@pytest.mark.parametrize("seed", range(100))
def test_turn_order_and_dot_path_follow_the_rules(seed):
    ch = generate_challenge(Settings(), rng=random.Random(seed))
    validate(ch.model_dump(mode="json", exclude_none=True), "session", "Challenge")
    assert sorted(ch.turn_order) == ["left", "right"]
    path = ch.dot_path
    assert len(path) == DOT_POINTS
    assert [p.t_ms for p in path] == [i * DOT_STEP_MS for i in range(DOT_POINTS)]
    for p in path:
        assert DOT_MARGIN <= p.x <= 1 - DOT_MARGIN and DOT_MARGIN <= p.y <= 1 - DOT_MARGIN
    for a, b in zip(path, path[1:], strict=False):
        assert math.dist((a.x, a.y), (b.x, b.y)) >= DOT_MIN_JUMP


def test_both_turn_orders_and_different_paths_occur():
    chs = [generate_challenge(Settings()) for _ in range(40)]
    assert {tuple(c.turn_order) for c in chs} == {("left", "right"), ("right", "left")}
    assert len({tuple((p.x, p.y) for p in c.dot_path) for c in chs}) == 40


def test_session_response_carries_the_new_fields(client):
    body, _ = start_session(client)
    validate(body, "session", "CreateSessionResponse")
    assert body["challenge"]["turn_order"] and body["challenge"]["dot_path"]


def test_refresh_gives_a_new_challenge_and_extends_the_token(client):
    body, auth = start_session(client)
    sid = body["session_id"]
    res = client.post(CHALLENGE.format(sid=sid), headers=auth)
    assert res.status_code == 200, res.text
    out = res.json()
    validate(out, "session", "ChallengeResponse")
    assert out["challenge"]["challenge_id"] != body["challenge"]["challenge_id"]
    assert out["expires_at"] >= body["expires_at"]


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


def test_refresh_does_not_escape_the_voice_step(client):
    """Đã bị đòi đọc câu thì lượt mặt mới (dù ra pass) vẫn phải đọc câu."""
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    assert client.post(FINALIZE.format(sid=sid), headers=auth).json()["status"] == "voice_challenge"
    client.post(CHALLENGE.format(sid=sid), headers=auth)
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(sid).scenario = "genuine"  # lượt mặt mới tự nó sẽ ra pass
    again = client.post(FINALIZE.format(sid=sid), headers=auth).json()
    assert again["status"] == "voice_challenge"


def test_refresh_after_a_scored_attempt_uses_up_a_retry(client):
    body, auth = start_session(client, "voice_clone")
    sid = body["session_id"]
    client.post(FINALIZE.format(sid=sid), headers=auth)
    for _ in range(3):
        client.post(CHALLENGE.format(sid=sid), headers=auth)
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
    body, auth = start_session(client, "genuine")
    sid = body["session_id"]
    with client.app.state.vericlue.transaction() as state:
        s = state.sessions.get(sid)
        s.voice_requested = s.voice_owed = True
    assert client.post(VOICE.format(sid=sid), headers=auth, files=AUDIO).json()["status"] == "pass"
    with client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).voice_owed is False
