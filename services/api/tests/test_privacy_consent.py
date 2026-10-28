"""SEC-06 tests only synthetic session data, actual AEAD and disposable SQLite."""

import base64
import io
import json
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import start_session
from contract_utils import validate
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from vericlue_api.core.config import get_settings
from vericlue_api.core.session_ingress import SessionMultipartParser
from vericlue_api.db.models import PrivacyEventRow, SessionKeyRow, utcnow
from vericlue_api.main import create_app
from vericlue_api.routers import privacy
from vericlue_api.services.privacy_consent import MAX_CONSENT_EVENTS
from vericlue_api.services.session_flow import SessionFlow


@pytest.fixture
def private_client(monkeypatch):
    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("REQUIRE_PRIVACY_CONSENT", "true")
    monkeypatch.setenv("PRIVACY_POLICY_VERSION", "test-v1")
    get_settings.cache_clear()
    app = create_app()
    # Parent integrates the router in main; keep this branch testable before wiring.
    if not any(getattr(r, "path", "") == "/v1/sessions/{session_id}/privacy" for r in app.routes):
        app.include_router(privacy.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def grant(client, sid, auth, categories, version="test-v1"):
    body = {"policy_version": version, "categories": categories, "consent": True}
    validate(body, "privacy", "PrivacyConsentRequest")
    r = client.post(f"/v1/sessions/{sid}/privacy/consent", headers=auth, json=body)
    if r.status_code == 200:
        validate(r.json(), "privacy", "PrivacyState")
    return r


def photo():
    out = io.BytesIO()
    Image.new("RGB", (64, 64), (100, 120, 140)).save(out, format="JPEG")
    return out.getvalue()


def upload_face(client, sid, auth):
    return client.post(
        f"/v1/sessions/{sid}/media",
        headers=auth,
        files={"image": ("face.jpg", photo(), "image/jpeg")},
    )


def withdraw(client, sid, auth):
    body = {"confirm": True}
    validate(body, "privacy", "PrivacyWithdrawalRequest")
    r = client.post(f"/v1/sessions/{sid}/privacy/withdraw", headers=auth, json=body)
    if r.status_code == 200:
        validate(r.json(), "privacy", "PrivacyState")
    return r


def test_receipt_is_versioned_idempotent_and_categories_expand_only_after_new_grant(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    initial = client.get(f"/v1/sessions/{sid}/privacy", headers=auth)
    assert initial.status_code == 200 and initial.json()["status"] == "not_granted"
    assert initial.json()["scope"] == "session"
    first = grant(client, sid, auth, ["face_biometrics"])
    assert first.status_code == 200
    again = grant(client, sid, auth, ["face_biometrics"])
    assert again.json() == first.json()
    expanded = grant(client, sid, auth, ["voice_biometrics"])
    assert expanded.status_code == 200
    assert expanded.json()["categories"] == ["face_biometrics", "voice_biometrics"]
    assert expanded.json()["consent_receipt_id"] != first.json()["consent_receipt_id"]
    with client.app.state.vericlue.database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(PrivacyEventRow)) == 2
        rows = list(db.scalars(select(PrivacyEventRow)))
        assert all(row.token_hash is None and row.token_expires_at is None for row in rows)
    assert expanded.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("endpoint", ["media", "id-card", "voice"])
def test_missing_category_blocks_before_multipart_parser(private_client, monkeypatch, endpoint):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]

    async def forbidden(self):
        raise AssertionError("Missing consent reached parser")

    monkeypatch.setattr(SessionMultipartParser, "parse", forbidden)
    r = client.post(
        f"/v1/sessions/{sid}/{endpoint}", headers=auth, files={"image": ("face.jpg", photo())}
    )
    assert r.status_code == 409 and r.json()["error_code"] == "privacy_consent_required"
    assert not (Path(client.app.state.vericlue.settings.media_dir) / sid).exists()


def test_contact_face_and_document_permissions_are_separate(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["id_document"]).status_code == 200
    assert upload_face(client, sid, auth).status_code == 409
    r = client.post(f"/v1/sessions/{sid}/otp", headers=auth, json={"phone": "0900000000"})
    assert r.status_code == 409
    assert grant(client, sid, auth, ["contact", "face_biometrics"]).status_code == 200
    assert (
        client.post(
            f"/v1/sessions/{sid}/otp", headers=auth, json={"phone": "0900000000"}
        ).status_code
        == 200
    )
    assert upload_face(client, sid, auth).status_code == 200


def test_voice_needs_explicit_voice_and_face_categories(private_client, monkeypatch):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200

    async def forbidden(self):
        raise AssertionError("Missing voice consent reached parser")

    monkeypatch.setattr(SessionMultipartParser, "parse", forbidden)
    r = client.post(
        f"/v1/sessions/{sid}/voice", headers=auth, files={"audio": ("voice.wav", b"synthetic")}
    )
    assert r.status_code == 409


def test_policy_change_requires_current_version_again(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200
    client.app.state.vericlue.settings.privacy_policy_version = "test-v2"
    assert upload_face(client, sid, auth).status_code == 409
    r = grant(client, sid, auth, ["face_biometrics"])
    assert r.status_code == 409 and r.json()["error_code"] == "privacy_policy_changed"
    assert grant(client, sid, auth, ["face_biometrics"], "test-v2").status_code == 200
    assert upload_face(client, sid, auth).status_code == 200


def collect_document(client, sid, auth):
    # Fictional card fields and generated JPEG; no identity/person data.
    response = client.post(
        f"/v1/sessions/{sid}/id-card",
        headers=auth,
        files={"front": ("front.jpg", photo()), "back": ("back.jpg", photo())},
        data={"qr": "000000000001||Nguoi Thu Nghiem|01011995|Nam|Dia Chi Tong Hop|01012020"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def collect_contact(client, sid, auth):
    sent = client.post(f"/v1/sessions/{sid}/otp", headers=auth, json={"phone": "0900000000"})
    assert sent.status_code == 200
    code = re.search(r"\b(\d{6})\b", sent.json()["simulated_sms"]).group(1)
    verified = client.post(f"/v1/sessions/{sid}/otp/verify", headers=auth, json={"code": code})
    assert verified.status_code == 200


def test_policy_change_cannot_reuse_collected_document_for_face_match(private_client, monkeypatch):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["id_document", "face_biometrics"]).status_code == 200
    collect_document(client, sid, auth)
    assert upload_face(client, sid, auth).status_code == 200
    root = client.app.state.vericlue
    root.settings.identity_lab_url = "http://identity.invalid"
    root.settings.privacy_policy_version = "test-v2"
    assert grant(client, sid, auth, ["face_biometrics"], "test-v2").status_code == 200

    def forbidden(*args, **kwargs):
        raise AssertionError("Old-policy card reached face matching")

    monkeypatch.setattr(SessionFlow, "finalize", forbidden)
    r = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
    assert r.status_code == 409 and r.json()["error_code"] == "privacy_consent_required"


@pytest.mark.parametrize("endpoint", ["finalize", "voice"])
def test_policy_change_cannot_reuse_verified_contact_for_enrollment(
    private_client, monkeypatch, endpoint
):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert (
        grant(client, sid, auth, ["contact", "id_document", "face_biometrics"]).status_code == 200
    )
    collect_document(client, sid, auth)
    collect_contact(client, sid, auth)
    root = client.app.state.vericlue
    with root.transaction() as state:
        state.sessions.get(sid).purpose = "onboarding"
    root.settings.account_enrollment = True
    root.settings.privacy_policy_version = "test-v2"
    # Regrant card and face/voice; old verified contact must still require fresh permission.
    assert (
        grant(
            client, sid, auth, ["id_document", "face_biometrics", "voice_biometrics"], "test-v2"
        ).status_code
        == 200
    )

    async def forbidden_parser(*args, **kwargs):
        raise AssertionError("Old-policy enrollment contact reached voice parser")

    def forbidden_finalize(*args, **kwargs):
        raise AssertionError("Old-policy enrollment contact reached inference/enrollment")

    monkeypatch.setattr(SessionMultipartParser, "parse", forbidden_parser)
    monkeypatch.setattr(SessionFlow, "finalize", forbidden_finalize)
    if endpoint == "voice":
        r = client.post(
            f"/v1/sessions/{sid}/voice", headers=auth, files={"audio": ("voice.wav", b"unused")}
        )
    else:
        r = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
    assert r.status_code == 409 and r.json()["error_code"] == "privacy_consent_required"


def test_face_only_processing_does_not_require_preissued_voice_or_unused_contact(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["contact", "face_biometrics"]).status_code == 200
    collect_contact(client, sid, auth)
    root = client.app.state.vericlue
    with root.transaction() as state:
        session = state.sessions.get(sid)
        session.voice_prompt = "Preissued but never recorded"
        session.voice_challenge_id = "vc_unused"
    root.settings.privacy_policy_version = "test-v2"
    assert grant(client, sid, auth, ["face_biometrics"], "test-v2").status_code == 200
    assert upload_face(client, sid, auth).status_code == 200
    assert client.post(f"/v1/sessions/{sid}/finalize", headers=auth).status_code == 200


@pytest.mark.parametrize(
    "patch",
    [
        {"consent": False},
        {"consent": 1},
        {"categories": []},
        {"categories": ["face_biometrics", "face_biometrics"]},
        {"categories": ["unknown"]},
        {"policy_version": ""},
        {"account_id": "arbitrary"},
    ],
)
def test_invalid_or_implicit_consent_is_rejected(private_client, patch):
    client = private_client
    s, auth = start_session(client)
    body = {
        "policy_version": "test-v1",
        "categories": ["face_biometrics"],
        "consent": True,
        **patch,
    }
    r = client.post(f"/v1/sessions/{s['session_id']}/privacy/consent", headers=auth, json=body)
    assert r.status_code == 422


def test_consent_ledger_is_bounded(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    root = client.app.state.vericlue
    for i in range(MAX_CONSENT_EVENTS):
        root.settings.privacy_policy_version = f"test-v{i}"
        assert grant(client, sid, auth, ["contact"], f"test-v{i}").status_code == 200
    root.settings.privacy_policy_version = "test-extra"
    r = grant(client, sid, auth, ["contact"], "test-extra")
    assert r.status_code == 409 and r.json()["error_code"] == "privacy_receipt_limit"


def test_withdrawal_shreds_key_blocks_work_and_honestly_reports_live_plaintext_lease(
    private_client,
):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    root = client.app.state.vericlue
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200
    assert upload_face(client, sid, auth).status_code == 200
    with root.transaction() as state:
        session = state.sessions.get(sid)
        prepared, lease = state.privacy.prepare(sid, {"images": session.images})
        plaintext = prepared["images"][0]
    try:
        r = withdraw(client, sid, auth)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["status"] == "withdrawn" and p["storage_erasure"] == "files_deleted"
        assert p["processing_cleanup"] == "not_verified"
        assert p["account_data_erased"] is False and p["credential_revocation"] == "not_performed"
        assert plaintext.exists()
        assert not (Path(root.settings.media_dir) / sid).exists()
        with root.database.sessions() as db:
            key = db.get(SessionKeyRow, sid)
            assert key.destroyed_at is not None and key.wrapped_key is None
        assert upload_face(client, sid, auth).status_code == 410
        assert client.post(f"/v1/sessions/{sid}/finalize", headers=auth).status_code == 410
        assert client.get(f"/v1/sessions/{sid}/result", headers=auth).status_code == 410
        assert (
            client.post(
                f"/v1/sessions/{sid}/credential-authorization", headers=auth, json={}
            ).status_code
            == 410
        )
        assert grant(client, sid, auth, ["face_biometrics"]).status_code == 410
        retry = withdraw(client, sid, auth)
        assert retry.status_code == 200 and retry.json() == p
        state = client.get(f"/v1/sessions/{sid}/privacy", headers=auth)
        assert state.status_code == 200 and state.json() == p
        with root.database.sessions() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(PrivacyEventRow)
                    .where(PrivacyEventRow.kind == "withdrawal")
                )
                == 1
            )
    finally:
        lease.release()
    assert not plaintext.exists()


def test_only_latest_bearer_can_withdraw_or_read_after_erasure(private_client):
    client = private_client
    s, old = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, old, ["face_biometrics"]).status_code == 200
    refreshed = client.post(f"/v1/sessions/{sid}/challenge", headers=old)
    assert refreshed.status_code == 200
    fresh = {"Authorization": "Bearer " + refreshed.json()["token"]}
    assert withdraw(client, sid, old).status_code == 401
    assert withdraw(client, sid, fresh).status_code == 200
    assert client.get(f"/v1/sessions/{sid}/privacy", headers=old).status_code == 401
    assert withdraw(client, sid, old).status_code == 401
    assert client.get(f"/v1/sessions/{sid}/privacy", headers=fresh).status_code == 200


def test_wrong_session_and_expired_receipt_credentials_are_rejected(private_client, monkeypatch):
    import vericlue_api.services.privacy_consent as privacy_service

    client = private_client
    s, auth = start_session(client)
    other, _ = start_session(client)
    assert (
        client.get(f"/v1/sessions/{other['session_id']}/privacy", headers=auth).status_code == 401
    )
    sid = s["session_id"]
    assert withdraw(client, sid, auth).status_code == 200
    monkeypatch.setattr(privacy_service, "utcnow", lambda: utcnow() + timedelta(days=1))
    assert client.get(f"/v1/sessions/{sid}/privacy", headers=auth).status_code == 401


def test_clock_rollback_does_not_make_withdrawal_receipt_reusable(private_client, monkeypatch):
    import vericlue_api.services.privacy_consent as privacy_service

    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert withdraw(client, sid, auth).status_code == 200
    monkeypatch.setattr(privacy_service, "utcnow", lambda: utcnow() - timedelta(days=1))
    assert client.get(f"/v1/sessions/{sid}/privacy", headers=auth).status_code == 401


def test_failed_withdrawal_commit_preserves_source_key_and_no_receipt(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    root = client.app.state.vericlue

    def fail_commit(connection):
        raise SQLAlchemyError("synthetic commit fault")

    event.listen(root.database.engine, "commit", fail_commit)
    try:
        r = withdraw(client, sid, auth)
        assert r.status_code == 503, r.text
    finally:
        event.remove(root.database.engine, "commit", fail_commit)
    with root.database.sessions() as db:
        assert db.get(SessionKeyRow, sid).wrapped_key is not None
        assert db.scalar(select(PrivacyEventRow).where(PrivacyEventRow.session_id == sid)) is None
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200
    assert upload_face(client, sid, auth).status_code == 200


def test_file_failure_does_not_undo_committed_withdrawal_and_retry_finishes(
    private_client, monkeypatch
):
    import vericlue_api.services.privacy_consent as privacy_service

    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200
    assert upload_face(client, sid, auth).status_code == 200
    original = privacy_service._delete_folder

    def fail(*args, **kwargs):
        raise PermissionError("synthetic file lock")

    monkeypatch.setattr(privacy_service, "_delete_folder", fail)
    first = withdraw(client, sid, auth)
    assert first.status_code == 200 and first.json()["storage_erasure"] == "key_destroyed"
    assert upload_face(client, sid, auth).status_code == 410
    monkeypatch.setattr(privacy_service, "_delete_folder", original)
    second = withdraw(client, sid, auth)
    assert second.status_code == 200 and second.json()["storage_erasure"] == "files_deleted"
    assert first.json()["withdrawal_receipt_id"] == second.json()["withdrawal_receipt_id"]


@pytest.mark.parametrize(
    "action", ["UPDATE privacy_events SET policy_version = 'changed'", "DELETE FROM privacy_events"]
)
def test_ledger_rejects_mutation(private_client, action):
    client = private_client
    s, auth = start_session(client)
    assert grant(client, s["session_id"], auth, ["contact"]).status_code == 200
    with pytest.raises(DBAPIError), client.app.state.vericlue.database.sessions.begin() as db:
        db.execute(text(action))


def test_receipts_contain_no_source_pii_or_bearer(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["contact"]).status_code == 200
    assert withdraw(client, sid, auth).status_code == 200
    with client.app.state.vericlue.database.sessions() as db:
        rows = list(db.scalars(select(PrivacyEventRow)))
        metadata = [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in rows]
    encoded = json.dumps(metadata, default=str)
    assert s["token"] not in encoded and "0900000000" not in encoded
    assert "template" not in encoded and "full_name" not in encoded


def test_privacy_json_is_small_and_unauthorized_body_is_not_read(private_client, monkeypatch):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    r = client.post(
        f"/v1/sessions/{sid}/privacy/consent",
        headers={**auth, "Content-Type": "application/json"},
        content=b" " * (8192 + 1),
    )
    assert r.status_code == 413
    consumed = []

    def stream():
        consumed.append(True)
        yield b" " * 1024

    r = client.post(
        f"/v1/sessions/{sid}/privacy/consent",
        headers={"Authorization": "Bearer invalid", "Content-Type": "application/json"},
        content=stream(),
    )
    assert r.status_code == 401
    assert consumed == []


def test_urlencoded_upload_cannot_bypass_multipart_rules(private_client, monkeypatch):
    from starlette.requests import Request

    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200

    async def forbidden(self, *args, **kwargs):
        raise AssertionError("Unsupported upload type reached Request.form")

    monkeypatch.setattr(Request, "_get_form", forbidden)
    r = client.post(f"/v1/sessions/{sid}/media", headers=auth, data={"image": "not-a-file"})
    assert r.status_code == 415 and r.json()["error_code"] == "unsupported_media_type"


def test_withdrawal_during_upload_blocks_second_auth_and_cannot_revive_key(
    private_client, monkeypatch
):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200
    original = SessionMultipartParser.parse

    async def withdraw_while_receiving(parser):
        from starlette.concurrency import run_in_threadpool

        r = await run_in_threadpool(withdraw, client, sid, auth)
        assert r.status_code == 200
        return await original(parser)

    monkeypatch.setattr(SessionMultipartParser, "parse", withdraw_while_receiving)
    assert upload_face(client, sid, auth).status_code == 410
    with client.app.state.vericlue.database.sessions() as db:
        key = db.get(SessionKeyRow, sid)
        assert key.wrapped_key is None and key.destroyed_at is not None


def test_concurrent_withdrawal_has_one_receipt_and_no_key_revival(private_client):
    client = private_client
    s, auth = start_session(client)
    sid = s["session_id"]
    assert grant(client, sid, auth, ["face_biometrics"]).status_code == 200
    assert upload_face(client, sid, auth).status_code == 200
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: withdraw(client, sid, auth), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert (
        responses[0].json()["withdrawal_receipt_id"] == responses[1].json()["withdrawal_receipt_id"]
    )
    with client.app.state.vericlue.database.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(PrivacyEventRow)
                .where(PrivacyEventRow.session_id == sid, PrivacyEventRow.kind == "withdrawal")
            )
            == 1
        )
        assert db.get(SessionKeyRow, sid).wrapped_key is None
