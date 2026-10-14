"""Luồng phiên eKYC qua HTTP: token Bearer, retry, voice, và 'không bao giờ lộ điểm số'."""

from __future__ import annotations

import json

import pytest
from conftest import start_session
from contract_utils import validate

FORBIDDEN_KEYS = {"score", "prob_attack", "gate", "modules", "suggestion", "evidence", "quality"}
FORBIDDEN_WORDS = ("giả mạo", "deepfake", "spoof", "attack")

SIGNALS = {
    "color_events": [{"index": 0, "rgb": "#ffcc73", "painted_at": 1234.5}],
    "frame_times": [{"capture_time": 1240.2, "presented_frames": 31, "media_time": 0.5}],
}
IMAGE = {"image": ("face.jpg", b"\xff\xd8\xff", "image/jpeg")}
AUDIO = {"audio": ("voice.wav", b"RIFF", "audio/wav")}


def keys_of(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from keys_of(v)
    elif isinstance(value, list):
        for v in value:
            yield from keys_of(v)


def assert_citizen_safe(res):
    """Phản hồi cho người dân: không điểm số, không chữ 'giả mạo'."""
    text = json.dumps(res.json(), ensure_ascii=False).lower()
    assert not set(keys_of(res.json())) & FORBIDDEN_KEYS
    assert not any(w in text for w in FORBIDDEN_WORDS)


def path(sid: str, step: str) -> str:
    return f"/v1/sessions/{sid}/{step}"


def run_finalize(client, scenario: str):
    body, auth = start_session(client, scenario)
    sid = body["session_id"]
    assert client.post(path(sid, "media"), headers=auth, files=IMAGE).status_code == 200
    assert client.post(path(sid, "signals"), headers=auth, json=SIGNALS).status_code == 200
    return sid, auth, client.post(path(sid, "finalize"), headers=auth)


def test_create_session_matches_contract(client):
    res = client.post("/v1/sessions")
    assert res.status_code == 200
    validate(res.json(), "session", "CreateSessionResponse")
    assert_citizen_safe(res)
    ch = res.json()["challenge"]
    assert len(ch["color_sequence"]) == 8 and "expires_at" in ch


def test_unknown_mock_scenario_is_rejected(client):
    res = client.post("/v1/sessions", headers={"X-Mock-Scenario": "nope"})
    assert res.status_code == 422 and res.json()["error_code"] == "unknown_scenario"


def test_scenario_header_ignored_when_not_mock(client, monkeypatch):
    from fastapi.testclient import TestClient

    from vericlue_api.core.config import get_settings
    from vericlue_api.main import create_app

    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    get_settings.cache_clear()
    res = TestClient(create_app()).post("/v1/sessions", headers={"X-Mock-Scenario": "nope"})
    assert res.status_code == 200


@pytest.mark.parametrize("step", ["media", "signals", "finalize", "voice"])
def test_every_session_step_requires_bearer(client, step):
    body, auth = start_session(client)
    url = path(body["session_id"], step)
    for headers in ({}, {"Authorization": "Bearer sai-token"}, {"Authorization": "Basic abc"}):
        res = client.post(url, headers=headers)
        assert res.status_code == 401
        validate(res.json(), "session", "ErrorResponse")


def test_token_of_another_session_is_rejected(client):
    a, _ = start_session(client)
    _, auth_b = start_session(client)
    res = client.post(path(a["session_id"], "finalize"), headers=auth_b)
    assert res.status_code == 401


def test_unknown_session_is_401_not_404(client):
    _, auth = start_session(client)
    assert client.post(path("ses_khong_co", "finalize"), headers=auth).status_code == 401


def test_genuine_session_passes_and_leaks_nothing(client):
    _, _, res = run_finalize(client, "genuine")
    assert res.status_code == 200
    validate(res.json(), "session", "FinalizeResponse")
    assert res.json() == {"status": "pass"}
    assert_citizen_safe(res)


def test_step_acks_match_contract(client):
    body, auth = start_session(client)
    sid = body["session_id"]
    media = client.post(path(sid, "media"), headers=auth, files=IMAGE)
    signals = client.post(path(sid, "signals"), headers=auth, json=SIGNALS)
    validate(media.json(), "session", "StepAck")
    validate(signals.json(), "session", "StepAck")
    assert media.json()["step"] == "media" and signals.json()["step"] == "signals"


def test_invalid_signals_body_is_422_with_error_format(client):
    body, auth = start_session(client)
    res = client.post(path(body["session_id"], "signals"), headers=auth, json={"x": 1})
    assert res.status_code == 422
    validate(res.json(), "session", "ErrorResponse")


@pytest.mark.parametrize("scenario", ["print", "replay", "faceswap", "virtual_cam", "error"])
def test_attack_scenarios_go_to_review_without_saying_why(client, scenario):
    _, _, res = run_finalize(client, scenario)
    assert res.json() == {"status": "review"}
    assert_citizen_safe(res)


def test_low_quality_retries_twice_then_review(client):
    sid, auth, first = run_finalize(client, "low_quality")
    a = first.json()
    validate(a, "session", "FinalizeResponse")
    assert a["status"] == "retry" and a["retry_hint"] == "MORE_LIGHT" and a["attempts_left"] == 1
    assert_citizen_safe(first)

    second = client.post(path(sid, "finalize"), headers=auth).json()
    validate(second, "session", "FinalizeResponse")
    assert second["status"] == "retry" and second["attempts_left"] == 0
    # mỗi lần chụp lại có thử thách MỚI
    ids = {a["challenge"]["challenge_id"], second["challenge"]["challenge_id"]}
    assert len(ids) == 2

    third = client.post(path(sid, "finalize"), headers=auth)
    assert third.json() == {"status": "review"}


def test_retry_hint_only_talks_about_quality(client):
    _, _, res = run_finalize(client, "low_quality")
    allowed = {
        "MORE_LIGHT",
        "MOVE_CLOSER",
        "MOVE_BACK",
        "FACE_CENTER",
        "HOLD_STILL",
        "QUIET_PLACE",
        "BRIGHTNESS_UP",
    }
    assert res.json()["retry_hint"] in allowed


def test_voice_clone_goes_through_voice_challenge_then_review(client):
    sid, auth, res = run_finalize(client, "voice_clone")
    body = res.json()
    validate(body, "session", "FinalizeResponse")
    assert body["status"] == "voice_challenge" and body["voice_prompt"]
    assert_citizen_safe(res)

    voice = client.post(path(sid, "voice"), headers=auth, files=AUDIO)
    assert voice.status_code == 200
    validate(voice.json(), "session", "VoiceResponse")
    assert voice.json() == {"status": "review"}
    assert_citizen_safe(voice)

    # ca vào bàn duyệt
    cases = client.get("/v1/review/cases").json()["items"]
    assert sid in {c["session_id"] for c in cases}


def test_genuine_voice_passes(client):
    sid, auth, _ = run_finalize(client, "genuine")
    voice = client.post(path(sid, "voice"), headers=auth, files=AUDIO)
    assert voice.json() == {"status": "pass"}


def test_review_case_from_session_has_priority_and_no_score(client):
    sid, _, _ = run_finalize(client, "virtual_cam")
    items = client.get("/v1/review/cases").json()["items"]
    mine = next(c for c in items if c["session_id"] == sid)
    assert mine["priority"] == "high"
    detail = client.get(f"/v1/review/cases/{mine['case_id']}")
    assert not set(keys_of(detail.json())) & {"score", "prob_attack", "gate", "modules"}


def test_uploads_are_stored_with_server_chosen_names(client, tmp_path):
    body, auth = start_session(client)
    sid = body["session_id"]
    evil = {"image": ("../../evil.php", b"x", "image/jpeg")}
    assert client.post(path(sid, "media"), headers=auth, files=evil).status_code == 200
    stored = sorted(p.name for p in (tmp_path / "media" / sid).iterdir())
    assert stored == ["face_image.bin"]
