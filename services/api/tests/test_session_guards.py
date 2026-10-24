"""PLAT-06: credentials, replay guards and evidence isolation between attempts."""

import base64
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from conftest import start_session
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.session_tokens import SessionTokenSigner, token_digest
from vericlue_api.db.models import DecisionRow, SessionRow
from vericlue_api.main import create_app
from vericlue_api.services import session_flow

IMAGE = {"image": ("face.jpg", b"first image", "image/jpeg")}
AUDIO = {"audio": ("voice.wav", b"first audio", "audio/wav")}
SIGNALS = {"color_events": [], "frame_times": []}


def endpoint(created, step):
    return f"/v1/sessions/{created['session_id']}/{step}"


def test_token_tampering_wrong_session_expiry_and_key_rotation():
    now = datetime(2026, 10, 24, tzinfo=UTC)
    signer = SessionTokenSigner(secrets.token_bytes(32))
    token = signer.issue("ses_one", now + timedelta(seconds=300))
    assert signer.verify(token, "ses_one", now=now)
    assert not signer.verify(token, "ses_two", now=now)
    assert not signer.verify(token, "ses_one", now=now + timedelta(seconds=300))
    assert not SessionTokenSigner(secrets.token_bytes(32)).verify(token, "ses_one", now=now)
    payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["exp"] += 3600
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    assert not signer.verify(f"{forged}.{signature}", "ses_one", now=now)


@pytest.mark.parametrize("token", ["", "a", "a.b.c", "é.x", "x" * 2049, "[].bad"])
def test_malformed_tokens_are_rejected(token):
    assert not SessionTokenSigner(secrets.token_bytes(32)).verify(token, "ses_one")


def test_concurrent_mock_requests_share_one_temporary_key():
    settings = Settings(_env_file=None, use_mock_models=True, session_signing_secret=None)
    ready = Barrier(8)
    expires = datetime.now(UTC) + timedelta(minutes=5)

    def issue(index):
        ready.wait(timeout=5)
        return index, settings.session_token_signer.issue(f"ses_{index}", expires)

    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(issue, range(8)))
    assert all(
        settings.session_token_signer.verify(token, f"ses_{index}") for index, token in tokens
    )


@pytest.mark.parametrize("secret", [None, "change-me"])
def test_real_mode_refuses_missing_or_weak_signing_secret(secret):
    settings = Settings(_env_file=None, use_mock_models=False, session_signing_secret=secret)
    with pytest.raises(ApiError) as error:
        _ = settings.session_token_signer
    assert error.value.status_code == 503


def test_db_contains_only_token_hash_and_another_valid_token_cannot_replace_it(client):
    created, auth = start_session(client)
    sid = created["session_id"]
    with client.app.state.vericlue.database.sessions() as db:
        payload = db.get(SessionRow, sid).payload
        assert "token" not in payload
        assert payload["token_hash"] == token_digest(created["token"])
        assert created["token"] not in json.dumps(payload)
    replacement = client.app.state.vericlue.settings.session_token_signer.issue(
        sid,
        datetime.fromisoformat(created["expires_at"]),
    )
    rejected = client.post(
        endpoint(created, "signals"),
        json=SIGNALS,
        headers={"Authorization": f"Bearer {replacement}"},
    )
    assert rejected.status_code == 401
    assert client.post(endpoint(created, "signals"), headers=auth, json=SIGNALS).status_code == 200


def test_expired_token_refuses_upload_without_writing_file(client, tmp_path):
    created, _ = start_session(client)
    expired = client.app.state.vericlue.settings.session_token_signer.issue(
        created["session_id"],
        datetime.now(UTC) - timedelta(seconds=1),
    )
    response = client.post(
        endpoint(created, "media"), files=IMAGE, headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401
    assert not (tmp_path / "media" / created["session_id"]).exists()


def test_legacy_unsigned_credentials_are_not_silently_reaccepted(client):
    created, auth = start_session(client)
    with client.app.state.vericlue.database.sessions.begin() as db:
        row = db.get(SessionRow, created["session_id"])
        payload = dict(row.payload)
        payload.pop("token_hash")
        payload["token"] = created["token"]
        row.payload = payload
    response = client.post(endpoint(created, "signals"), headers=auth, json=SIGNALS)
    assert response.status_code == 401


def test_voice_challenge_expiring_during_inference_cannot_pass(client, monkeypatch):
    created, auth = start_session(client, "voice_clone")
    assert (
        client.post(endpoint(created, "finalize"), headers=auth).json()["status"]
        == "voice_challenge"
    )
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        session.scenario = "genuine"
        expiry = session.voice_expires_at

    class Clock(datetime):
        finished = False

        @classmethod
        def now(cls, tz=None):
            return expiry + timedelta(seconds=1) if cls.finished else datetime.now(tz)

    monkeypatch.setattr(session_flow, "datetime", Clock)
    original = client.app.state.vericlue.orchestrator.run

    def complete_after_expiration(*args, **kwargs):
        result = original(*args, **kwargs)
        Clock.finished = True
        return result

    monkeypatch.setattr(client.app.state.vericlue.orchestrator, "run", complete_after_expiration)
    response = client.post(endpoint(created, "voice"), headers=auth, files=AUDIO)
    assert response.status_code == 200 and response.json() == {"status": "review"}


def test_replayed_media_and_signals_do_not_replace_accepted_data(client):
    created, auth = start_session(client)
    assert client.post(endpoint(created, "media"), headers=auth, files=IMAGE).status_code == 200
    again = client.post(
        endpoint(created, "media"),
        headers=auth,
        files={"image": ("face.jpg", b"replacement", "image/jpeg")},
    )
    assert again.status_code == 409
    assert again.json()["error_code"] == "step_already_received"
    assert client.post(endpoint(created, "signals"), headers=auth, json=SIGNALS).status_code == 200
    assert (
        client.post(
            endpoint(created, "signals"),
            headers=auth,
            json={"color_events": [{"changed": True}], "frame_times": []},
        ).status_code
        == 409
    )
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert session.images[0].read_bytes() == b"first image"
        assert session.signals == SIGNALS


def test_pass_closes_every_step_and_does_not_record_another_decision(client):
    created, auth = start_session(client)
    assert client.post(endpoint(created, "finalize"), headers=auth).json() == {"status": "pass"}
    for step, kwargs in [
        ("media", {"files": IMAGE}),
        ("signals", {"json": SIGNALS}),
        ("finalize", {}),
        ("voice", {"files": AUDIO}),
    ]:
        response = client.post(endpoint(created, step), headers=auth, **kwargs)
        assert response.status_code == 409
        assert response.json()["error_code"] == "session_closed"
    with client.app.state.vericlue.database.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(DecisionRow)
                .where(DecisionRow.session_id == created["session_id"])
            )
            == 1
        )


def test_retry_discards_previous_evidence_and_accepts_new_capture(client):
    created, auth = start_session(client, "low_quality")
    assert (
        client.post(
            endpoint(created, "media"),
            headers=auth,
            files={**IMAGE, "video": ("face.webm", b"old video", "video/webm")},
        ).status_code
        == 200
    )
    assert client.post(endpoint(created, "signals"), headers=auth, json=SIGNALS).status_code == 200
    retried = client.post(endpoint(created, "finalize"), headers=auth).json()
    assert retried["status"] == "retry"
    assert retried["challenge"]["challenge_id"] != created["challenge"]["challenge_id"]
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert not session.images and session.video is None and session.audio is None
        assert session.signals == {} and session.results == {} and session.accepted_steps == []
    assert client.post(endpoint(created, "media"), headers=auth, files=IMAGE).status_code == 200
    assert client.post(endpoint(created, "signals"), headers=auth, json=SIGNALS).status_code == 200


@pytest.mark.parametrize("step", ["media", "signals", "finalize"])
def test_expired_face_challenge_rejects_step_before_writing_or_deciding(client, tmp_path, step):
    created, auth = start_session(client)
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(created["session_id"]).challenge.expires_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
    kwargs = {"files": IMAGE} if step == "media" else {"json": SIGNALS} if step == "signals" else {}
    response = client.post(endpoint(created, step), headers=auth, **kwargs)
    assert response.status_code == 409 and response.json()["error_code"] == "challenge_expired"
    assert not (tmp_path / "media" / created["session_id"]).exists()


def test_voice_attempt_blocks_face_steps_and_expires_without_file_write(client, tmp_path):
    created, auth = start_session(client, "voice_clone")
    assert (
        client.post(endpoint(created, "finalize"), headers=auth).json()["status"]
        == "voice_challenge"
    )
    for step, kwargs in [
        ("media", {"files": IMAGE}),
        ("signals", {"json": SIGNALS}),
        ("finalize", {}),
    ]:
        response = client.post(endpoint(created, step), headers=auth, **kwargs)
        assert response.status_code == 409
    with client.app.state.vericlue.transaction() as state:
        state.sessions.get(created["session_id"]).voice_expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
    response = client.post(endpoint(created, "voice"), headers=auth, files=AUDIO)
    assert response.status_code == 409 and response.json()["error_code"] == "challenge_expired"
    assert not (tmp_path / "media" / created["session_id"]).exists()


def test_duplicate_step_guard_survives_application_restart(client):
    created, auth = start_session(client)
    assert client.post(endpoint(created, "signals"), headers=auth, json=SIGNALS).status_code == 200
    with TestClient(create_app()) as restarted:
        response = restarted.post(endpoint(created, "signals"), headers=auth, json=SIGNALS)
        assert (
            response.status_code == 409 and response.json()["error_code"] == "step_already_received"
        )


def test_oversized_optional_video_does_not_write_first_image(client, tmp_path):
    client.app.state.vericlue.settings.max_upload_mb = 1
    created, auth = start_session(client)
    response = client.post(
        endpoint(created, "media"),
        headers=auth,
        files={**IMAGE, "video": ("face.webm", b"0" * (1024 * 1024 + 1), "video/webm")},
    )
    assert response.status_code == 413
    assert not (tmp_path / "media" / created["session_id"]).exists()
    assert client.post(endpoint(created, "media"), headers=auth, files=IMAGE).status_code == 200
