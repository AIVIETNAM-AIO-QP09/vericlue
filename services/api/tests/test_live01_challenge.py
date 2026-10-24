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
