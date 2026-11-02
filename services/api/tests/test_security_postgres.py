"""Security regressions on PostgreSQL; skip honestly without TEST_DATABASE_URL."""

import base64
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier, Event

import pytest
from conftest import start_session
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from synthetic_images import synthetic_image
from test_db_postgres import postgres as postgres
from test_upload_image_safety import card

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import (
    AccountRow,
    AccountTemplateConsentRow,
    PrivacyEventRow,
    SessionKeyRow,
    SessionRow,
    utcnow,
)
from vericlue_api.main import create_app
from vericlue_api.services import identity_steps
from vericlue_api.services.privacy_consent import PrivacyService

POLICY = "pg-security-v1"


@pytest.fixture
def secured_client(postgres, monkeypatch):
    monkeypatch.setenv("PRODUCT_MODE", "ekyc")
    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("REQUIRE_PRIVACY_CONSENT", "true")
    monkeypatch.setenv("PRIVACY_POLICY_VERSION", POLICY)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def granted(client):
    created, auth = start_session(client)
    sid = created["session_id"]
    response = client.post(
        f"/v1/sessions/{sid}/privacy/consent",
        headers=auth,
        json={
            "policy_version": POLICY,
            "categories": ["contact", "id_document", "face_biometrics", "voice_biometrics"],
            "consent": True,
        },
    )
    assert response.status_code == 200, response.text
    return sid, auth


def withdraw(client, sid, auth):
    return client.post(f"/v1/sessions/{sid}/privacy/withdraw", headers=auth, json={"confirm": True})


def test_postgres_account_template_consent_race_immutable_ledger_and_account_fk(
    postgres, secured_client
):
    client = secured_client
    created = client.post(
        "/v1/sessions", json={"purpose": "onboarding", "nonce": secrets.token_hex(16)}
    )
    assert created.status_code == 200, created.text
    sid = created.json()["session_id"]
    auth = {"Authorization": "Bearer " + created.json()["token"]}
    response = client.post(
        f"/v1/sessions/{sid}/privacy/consent",
        headers=auth,
        json={
            "policy_version": POLICY,
            "categories": ["contact", "id_document", "face_biometrics", "voice_biometrics"],
            "consent": True,
        },
    )
    assert response.status_code == 200, response.text
    ready = Barrier(2)

    def grant_template(_):
        ready.wait(timeout=10)
        return client.post(
            f"/v1/sessions/{sid}/privacy/account-template/consent",
            headers=auth,
            json={
                "policy_version": client.app.state.vericlue.settings.account_template_policy_version,
                "purpose": "account_template",
                "consent": True,
            },
        )

    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(grant_template, range(2)))
    for response in responses:
        assert response.status_code == 200, response.text
    receipt = responses[0].json()["consent_receipt_id"]
    assert responses[0].json() == responses[1].json()
    account_id = "pg_consent_" + secrets.token_hex(12)
    with postgres.sessions.begin() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AccountTemplateConsentRow)
                .where(AccountTemplateConsentRow.session_id == sid)
            )
            == 1
        )
        original_policy = db.get(AccountTemplateConsentRow, receipt).policy_version
        db.add(
            AccountRow(
                account_id=account_id,
                source_session_id=sid,
                consent_receipt_id=receipt,
                device_id="pg_device_" + secrets.token_hex(12),
                expires_at=utcnow() + timedelta(days=1),
            )
        )
    for statement in (
        "UPDATE account_template_consents SET policy_version = 'tampered' WHERE receipt_id = :receipt",
        "DELETE FROM account_template_consents WHERE receipt_id = :receipt",
    ):
        with pytest.raises(DBAPIError) as error, postgres.sessions.begin() as db:
            db.execute(text(statement), {"receipt": receipt})
        assert error.value.orig.sqlstate == "P0001"
    with pytest.raises(DBAPIError) as error, postgres.sessions.begin() as db:
        db.execute(
            text("UPDATE accounts SET consent_receipt_id = :missing WHERE account_id = :account"),
            {"missing": "prv_" + secrets.token_hex(16), "account": account_id},
        )
    assert error.value.orig.sqlstate == "23503"
    assert error.value.orig.diag.constraint_name == "fk_accounts_consent_receipt_id"
    with postgres.sessions() as db:
        assert db.get(AccountTemplateConsentRow, receipt).policy_version == original_policy
        assert db.get(AccountRow, account_id).consent_receipt_id == receipt


def test_postgres_privacy_migration_blocks_ledger_mutation_and_duplicate_withdrawal(
    postgres, secured_client
):
    client = secured_client
    sid, auth = granted(client)
    for statement in (
        "UPDATE privacy_events SET policy_version = 'changed' WHERE session_id = :sid",
        "DELETE FROM privacy_events WHERE session_id = :sid",
    ):
        with pytest.raises(DBAPIError) as error, postgres.sessions.begin() as db:
            db.execute(text(statement), {"sid": sid})
        assert error.value.orig.sqlstate == "P0001"
    response = withdraw(client, sid, auth)
    assert response.status_code == 200, response.text
    with pytest.raises(DBAPIError) as error, postgres.sessions.begin() as db:
        db.add(
            PrivacyEventRow(
                receipt_id="prv_" + secrets.token_hex(16),
                session_id=sid,
                kind="withdrawal",
                policy_version=POLICY,
                categories=[],
                recorded_at=utcnow(),
            )
        )
        db.flush()
    assert error.value.orig.sqlstate == "23505"
    assert error.value.orig.diag.constraint_name == "uq_privacy_withdrawal"
    with postgres.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(PrivacyEventRow)
                .where(PrivacyEventRow.session_id == sid, PrivacyEventRow.kind == "withdrawal")
            )
            == 1
        )


def test_postgres_withdrawal_waits_for_snapshot_writer_and_blocks_key_revival(
    postgres, secured_client
):
    client = secured_client
    root = client.app.state.vericlue
    sid, auth = granted(client)
    token = auth["Authorization"].removeprefix("Bearer ")
    locked, release = Event(), Event()

    def write_snapshot():
        with root.transaction() as state:
            session = state.sessions.get(sid)
            session.uploaded_media_bytes += 1
            locked.set()
            assert release.wait(10)

    with ThreadPoolExecutor(1) as pool:
        writer = pool.submit(write_snapshot)
        try:
            assert locked.wait(5)
            with pytest.raises(DBAPIError) as error, postgres.sessions.begin() as db:
                db.execute(text("SELECT set_config('lock_timeout', '250ms', true)"))
                PrivacyService(root.settings, db).withdraw(sid, token)
            assert error.value.orig.sqlstate == "55P03"
            with postgres.sessions() as db:
                assert db.get(SessionKeyRow, sid).wrapped_key is not None
                assert (
                    db.scalar(
                        select(PrivacyEventRow).where(
                            PrivacyEventRow.session_id == sid, PrivacyEventRow.kind == "withdrawal"
                        )
                    )
                    is None
                )
        finally:
            release.set()
        writer.result(timeout=10)
    response = withdraw(client, sid, auth)
    assert response.status_code == 200, response.text
    with postgres.sessions() as db:
        erased_snapshot = db.get(SessionRow, sid).payload
    # Both snapshot-reading and snapshot-writing endpoints must stop before a
    # later ApplicationState.save_all can recreate the erased DEK or payload.
    assert client.get(f"/v1/sessions/{sid}/result", headers=auth).status_code == 410
    assert client.post(f"/v1/sessions/{sid}/challenge", headers=auth).status_code == 410
    with postgres.sessions() as db:
        key = db.get(SessionKeyRow, sid)
        assert key.wrapped_key is None and key.destroyed_at is not None
        assert db.get(SessionRow, sid).payload == erased_snapshot


def test_postgres_card_and_face_transactions_share_the_same_cumulative_quota(
    postgres, secured_client, monkeypatch
):
    client = secured_client
    root = client.app.state.vericlue
    root.settings.max_session_media_mb = 1
    sid, auth = granted(client)
    image = synthetic_image()
    with root.transaction() as state:
        state.sessions.get(sid).uploaded_media_bytes = 1024 * 1024 - 4 * len(image)
    locked, release, face_started = Event(), Event(), Event()
    original_save = identity_steps.save_upload

    def hold_card_write(*args, **kwargs):
        if args[2].startswith("id_front"):
            locked.set()
            assert release.wait(10)
        return original_save(*args, **kwargs)

    def send_face():
        face_started.set()
        return client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("face.bin", image), "video": ("face.webm", image)},
        )

    monkeypatch.setattr(identity_steps, "save_upload", hold_card_write)
    with ThreadPoolExecutor(2) as pool:
        scanned = pool.submit(card, client, sid, auth)
        try:
            assert locked.wait(5)
            face = pool.submit(send_face)
            assert face_started.wait(5)
        finally:
            release.set()
        assert scanned.result(timeout=10).status_code == 200
        rejected = face.result(timeout=10)
        assert rejected.status_code == 413
        assert rejected.json()["error_code"] == "session_media_quota_exceeded"
    with root.transaction() as state:
        session = state.sessions.get(sid)
        assert session.uploaded_media_bytes == 1024 * 1024
        assert session.id_scan_count == 1
        assert not session.images and session.video is None
        assert set((Path(root.settings.media_dir) / sid).iterdir()) == {
            session.id_front,
            session.id_back,
        }
