"""SEC-01 uses synthetic identities/images only; real crypto, SQLite migration and API."""

import base64
import io
import json
import secrets
from concurrent.futures import Future
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import (
    AccessEventRow,
    ModuleResultRow,
    ReviewEventRow,
    SessionKeyRow,
    SessionRow,
    utcnow,
)
from vericlue_api.main import create_app
from vericlue_api.services.audit_log import ChainEvent, verify_chain
from vericlue_api.services.session_privacy import MAGIC, SessionPrivacy
from vericlue_api.services.storage import cleanup_expired


@pytest.fixture
def private_client(monkeypatch):
    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    token = secrets.token_urlsafe(32)
    monkeypatch.setenv("STAFF_ACCESS_TOKENS", json.dumps({token: "staff-synthetic"}))
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        client.staff_auth = {"Authorization": "Bearer " + token}
        yield client


def start(client, scenario="genuine"):
    response = client.post("/v1/sessions", headers={"X-Mock-Scenario": scenario})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["session_id"], {"Authorization": "Bearer " + body["token"]}


def image_bytes():
    output = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "Synthetic private device"
    Image.new("RGB", (64, 64), (100, 120, 140)).save(output, format="JPEG", exif=exif)
    return output.getvalue()


def test_sensitive_snapshot_media_and_result_are_encrypted(private_client):
    client = private_client
    sid, auth = start(client)
    image = image_bytes()
    sent = client.post(
        f"/v1/sessions/{sid}/id-card",
        headers=auth,
        files={
            "front": ("front.jpg", image, "image/jpeg"),
            "back": ("back.jpg", image, "image/jpeg"),
        },
        data={
            "qr": "001099012345|123456789|Synthetic Person|01011995|Nam|Synthetic address|15062021"
        },
    )
    assert sent.status_code == 200, sent.text
    response = client.post(
        f"/v1/sessions/{sid}/media",
        headers=auth,
        files={"image": ("face.jpg", image, "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        assert session.id_fields["full_name"] == "Synthetic Person"
        original = session.images[0]
        assert original.read_bytes().startswith(MAGIC)
        prepared, lease = state.privacy.prepare(sid, {"images": [original]})
        try:
            with Image.open(prepared["images"][0]) as clean:
                assert not clean.getexif()
                assert clean.size == (64, 64)
        finally:
            lease.release()
    response = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
    assert response.status_code == 200 and response.json()["status"] == "pass", response.text
    assert "score" not in response.text
    with client.app.state.vericlue.database.sessions() as db:
        row = db.get(SessionRow, sid)
        assert set(row.payload) == {"encrypted_session_v1"}
        assert "Synthetic Person" not in json.dumps(row.payload)
        assert "token_hash" not in row.payload
        results = list(db.scalars(select(ModuleResultRow).where(ModuleResultRow.session_id == sid)))
        assert results and all(set(r.payload) == {"encrypted_session_v1"} for r in results)
        assert all(r.evidence == [] and r.quality == {} for r in results)


@pytest.mark.parametrize("fault", ["tamper", "session", "purpose", "master", "plain"])
def test_wrong_binding_configuration_or_ciphertext_cannot_be_read(private_client, fault):
    root = private_client.app.state.vericlue
    sid, _ = start(private_client)
    with root.transaction() as state:
        protected = state.privacy.seal_json(sid, "test", {"name": "Synthetic secret"})
        settings = root.settings
        if fault == "tamper":
            raw = bytearray(base64.b64decode(protected["encrypted_session_v1"]))
            raw[-1] ^= 1
            protected["encrypted_session_v1"] = base64.b64encode(raw).decode()
        elif fault == "master":
            settings = settings.model_copy(
                update={
                    "session_master_key": Settings(
                        session_master_key=base64.b64encode(secrets.token_bytes(32)).decode()
                    ).session_master_key
                }
            )
        elif fault == "plain":
            protected = {"name": "Synthetic secret"}
        privacy = SessionPrivacy(settings, state.db)
        with pytest.raises(ApiError) as error:
            privacy.open_json(
                "ses_other" if fault == "session" else sid,
                "other" if fault == "purpose" else "test",
                protected,
            )
        assert error.value.error_code == "privacy_unavailable"


def test_key_destruction_is_a_tombstone_and_unreadable(private_client):
    sid, _ = start(private_client)
    root = private_client.app.state.vericlue
    with root.transaction() as state:
        protected = state.privacy.seal_json(sid, "test", {"synthetic": True})
        state.privacy.destroy(sid)
    with root.transaction() as state:
        row = state.db.get(SessionKeyRow, sid)
        assert row.wrapped_key is None and row.destroyed_at is not None
        with pytest.raises(ApiError):
            state.privacy.open_json(sid, "test", protected)
        with pytest.raises(ApiError):
            state.privacy.seal_json(sid, "test", {"replacement": True})


def test_temp_file_lives_until_late_native_future_finishes(private_client):
    sid, auth = start(private_client)
    root = private_client.app.state.vericlue
    assert (
        private_client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("face.jpg", image_bytes(), "image/jpeg")},
        ).status_code
        == 200
    )
    with root.transaction() as state:
        session = state.sessions.get(sid)
        prepared, lease = state.privacy.prepare(sid, {"images": session.images})
        decoded = prepared["images"][0]
        future = Future()
        lease.retain(future)
        lease.release()  # HTTP request returns, but native job still owns the file.
        assert decoded.exists()
        future.set_result(None)
        assert not decoded.exists()


def test_ttl_destroys_key_and_deletes_media(private_client):
    client = private_client
    sid, auth = start(client)
    assert (
        client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("face.jpg", image_bytes(), "image/jpeg")},
        ).status_code
        == 200
    )
    root = client.app.state.vericlue
    with root.database.sessions.begin() as db:
        row = db.get(SessionRow, sid)
        row.last_activity_at = utcnow() - timedelta(hours=25)
    cleanup_expired(root.database, root.settings)
    with root.database.sessions() as db:
        assert db.get(SessionKeyRow, sid).wrapped_key is None
        assert db.get(SessionRow, sid).media_deleted_at is not None
    assert not (Path(root.settings.media_dir) / sid).exists()


def test_review_requires_staff_credentials_and_logs_verified_actor(private_client):
    client = private_client
    assert client.get("/v1/review/cases").status_code == 401
    _, citizen_auth = start(client)
    assert client.get("/v1/review/cases", headers=citizen_auth).status_code == 401
    records = client.get("/v1/review/cases", headers=client.staff_auth).json()["items"]
    case = records[0]["case_id"]
    assert client.get(f"/v1/review/cases/{case}", headers=client.staff_auth).status_code == 200
    assert (
        client.post(
            f"/v1/review/cases/{case}/initial",
            headers=client.staff_auth,
            json={"decision": "accept", "note": "Synthetic confidential note"},
        ).status_code
        == 200
    )
    assert (
        "Synthetic confidential note"
        in client.get(f"/v1/review/cases/{case}", headers=client.staff_auth).text
    )
    with client.app.state.vericlue.database.sessions() as db:
        events = list(db.scalars(select(AccessEventRow).order_by(AccessEventRow.id)))
        assert events and all(e.actor == "staff-synthetic" for e in events)
        for scope in {e.scope for e in events}:
            assert verify_chain(
                [ChainEvent(e.prev_hash, e.hash, e.payload) for e in events if e.scope == scope]
            ).ok
        note = db.scalar(select(ReviewEventRow).where(ReviewEventRow.case_id == case))
        assert note.note is None and "Synthetic confidential note" not in json.dumps(note.payload)
        assert note.actor == "staff-synthetic"


@pytest.mark.parametrize(
    "action", ["UPDATE access_events SET actor='changed'", "DELETE FROM access_events"]
)
def test_access_audit_database_rejects_mutation(private_client, action):
    client = private_client
    assert client.get("/v1/review/cases", headers=client.staff_auth).status_code == 200
    with pytest.raises(DBAPIError), client.app.state.vericlue.database.engine.begin() as db:
        db.execute(text(action))


def test_missing_master_never_creates_plaintext_session(private_client, monkeypatch):
    root = private_client.app.state.vericlue
    monkeypatch.setattr(root.settings, "session_master_key", None)
    response = private_client.post("/v1/sessions")
    assert response.status_code == 503 and response.json()["error_code"] == "privacy_unavailable"


def test_staff_preflight_and_encoded_route_are_protected(private_client):
    client = private_client
    response = client.options(
        "/v1/review/cases",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert client.get("/v1/review%2Fcases").status_code == 401


def test_expired_review_keeps_listing_metadata_without_decrypting(private_client):
    client = private_client
    record = client.get("/v1/review/cases", headers=client.staff_auth).json()["items"][0]
    with client.app.state.vericlue.transaction() as state:
        state.privacy.destroy(record["session_id"])
    assert client.get("/v1/review/cases", headers=client.staff_auth).status_code == 200
    response = client.get(f"/v1/review/cases/{record['case_id']}", headers=client.staff_auth)
    assert response.status_code == 410 and response.json()["error_code"] == "data_expired"
    check = client.get(
        f"/v1/review/cases/{record['case_id']}/audit/verify", headers=client.staff_auth
    )
    assert check.status_code == 200 and check.json()["ok"]


def test_actual_orchestrator_keeps_media_for_timed_out_native_job(private_client):
    import threading
    from time import monotonic, sleep

    from vericlue_api.services.orchestrator import Orchestrator
    from vericlue_ml.common.result import Module, ModuleResult
    from vericlue_ml.mock.detectors import MockDetector

    client = private_client
    sid, auth = start(client)
    assert (
        client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("face.jpg", image_bytes(), "image/jpeg")},
        ).status_code
        == 200
    )
    ready, release = threading.Event(), threading.Event()
    observed = []

    class Detector:
        name, version = "quality", "synthetic"

        def predict(self, inp):
            observed.append(inp.images[0])
            ready.set()
            assert release.wait(3)
            assert inp.images[0].read_bytes().startswith(b"\xff\xd8")
            return ModuleResult(
                module="quality", model_version=self.version, status="ok", gate="pass", latency_ms=0
            )

    orchestrator = Orchestrator(
        Settings(detector_timeout_seconds=0.1),
        detector_factory=lambda m: Detector() if m == Module.QUALITY else MockDetector(m),
    )
    orchestrator.start()
    try:
        with client.app.state.vericlue.transaction() as state:
            session = state.sessions.get(sid)
            prepared, lease = state.privacy.prepare(sid, {"images": session.images})
            result = orchestrator.run(
                [Module.QUALITY], session_id=sid, scenario="genuine", **prepared, media_lease=lease
            )
            lease.release()
            assert result[Module.QUALITY].error_code == "E_TIMEOUT" and ready.is_set()
            assert observed[0].exists()
            release.set()
            deadline = monotonic() + 2
            while observed[0].exists() and monotonic() < deadline:
                sleep(0.01)
            assert not observed[0].exists()
    finally:
        release.set()
        orchestrator.close()


def test_identity_is_masked_then_explicit_reveal_is_audited(private_client):
    from contract_utils import validate

    client = private_client
    sid, auth = start(client, "print")
    image = image_bytes()
    assert (
        client.post(
            f"/v1/sessions/{sid}/id-card",
            headers=auth,
            files={
                "front": ("front.jpg", image, "image/jpeg"),
                "back": ("back.jpg", image, "image/jpeg"),
            },
            data={
                "qr": "001099012345|123456789|Synthetic Person|01011995|Nam|Synthetic address|15062021"
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("face.jpg", image, "image/jpeg")},
        ).status_code
        == 200
    )
    assert client.post(f"/v1/sessions/{sid}/finalize", headers=auth).json()["status"] == "review"
    records = client.get("/v1/review/cases", headers=client.staff_auth).json()["items"]
    case_id = next(r["case_id"] for r in records if r["session_id"] == sid)
    path = f"/v1/review/cases/{case_id}/identity"
    assert client.get(path, headers=auth).status_code == 401
    masked = client.get(path, headers=client.staff_auth)
    assert masked.status_code == 200, masked.text
    validate(masked.json(), "review", "ReviewIdentity")
    assert masked.json()["id_number"] == "*********345"
    assert masked.json()["date_of_birth"] == "1995"
    revealed = client.post(path + "/reveal", headers=client.staff_auth)
    assert revealed.status_code == 200, revealed.text
    validate(revealed.json(), "review", "ReviewIdentity")
    assert revealed.json()["id_number"] == "001099012345" and not revealed.json()["masked"]
    assert revealed.json()["date_of_birth"] == "1995-01-01"
    with client.app.state.vericlue.database.sessions() as db:
        events = list(db.scalars(select(AccessEventRow).where(AccessEventRow.scope == sid)))
        assert any(e.action == "identity_masked" for e in events)
        assert sum(e.action == "identity_revealed" for e in events) == 1
        assert "001099012345" not in json.dumps(db.get(SessionRow, sid).payload)
