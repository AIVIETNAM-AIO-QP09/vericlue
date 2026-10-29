"""Retention cannot delete a directory while a serialized upload can recreate it."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event

import pytest
from conftest import start_session
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from synthetic_images import synthetic_image
from test_session_privacy import private_client as private_client

from vericlue_api.db.models import CleanupAuditRow, SessionKeyRow, SessionRow, utcnow
from vericlue_api.services import session_flow, storage


@pytest.fixture(autouse=True)
def ekyc_mode(monkeypatch):
    monkeypatch.setenv("PRODUCT_MODE", "ekyc")
    monkeypatch.setenv("MEDIA_TTL_UNVERIFIED_HOURS", "24")


def test_sqlite_retention_waits_for_upload_before_deleting_media(private_client, monkeypatch):
    client = private_client
    root = client.app.state.vericlue
    root.settings.product_mode = "ekyc"
    root.settings.media_ttl_unverified_hours = 24
    created, auth = start_session(client)
    sid = created["session_id"]
    paused, release, cleaner_started, deleting = Event(), Event(), Event(), Event()
    original_save, original_delete = session_flow.save_upload, storage._delete_folder

    def pause_save(*args, **kwargs):
        paused.set()
        assert release.wait(5)
        return original_save(*args, **kwargs)

    def observe_delete(*args, **kwargs):
        deleting.set()
        return original_delete(*args, **kwargs)

    def expire_after_authorization():
        cleaner_started.set()
        return storage.cleanup_expired(
            root.database, root.settings, now=utcnow() + timedelta(days=2)
        )

    monkeypatch.setattr(session_flow, "save_upload", pause_save)
    monkeypatch.setattr(storage, "_delete_folder", observe_delete)
    with ThreadPoolExecutor(2) as pool:
        upload = pool.submit(
            client.post,
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("synthetic.bin", synthetic_image())},
        )
        try:
            assert paused.wait(5)
            cleanup = pool.submit(expire_after_authorization)
            assert cleaner_started.wait(5)
            # Simulate crossing the deadline after request authentication. The
            # cleaner must wait for the entire upload transaction, not only its
            # final DB update after files have already been removed.
            assert not deleting.wait(0.3)
        finally:
            release.set()
        assert upload.result().status_code == 200
        assert len(cleanup.result()) == 1
    assert deleting.is_set()
    assert not (Path(root.settings.media_dir) / sid).exists()
    with root.database.sessions() as db:
        assert db.get(SessionRow, sid).media_deleted_at is not None
        key = db.get(SessionKeyRow, sid)
        assert key.wrapped_key is None and key.destroyed_at is not None


@pytest.mark.parametrize("private", [True, False])
def test_failed_unlink_does_not_delay_key_erasure_and_files_are_retried(
    request, monkeypatch, private
):
    client = request.getfixturevalue("private_client" if private else "client")
    root = client.app.state.vericlue
    root.settings.product_mode = "ekyc"
    root.settings.media_ttl_unverified_hours = 24
    created, auth = start_session(client)
    sid = created["session_id"]
    assert (
        client.post(
            f"/v1/sessions/{sid}/media",
            headers=auth,
            files={"image": ("synthetic.bin", synthetic_image())},
        ).status_code
        == 200
    )
    expiry = utcnow() + timedelta(days=2)
    folder = Path(root.settings.media_dir) / sid

    def fail_unlink(*_args, **_kwargs):
        raise PermissionError("Synthetic file lock")

    with monkeypatch.context() as patch:
        patch.setattr(storage, "_delete_folder", fail_unlink)
        assert storage.cleanup_expired(root.database, root.settings, now=expiry) == []
    assert folder.exists()
    with root.database.sessions() as db:
        assert db.get(SessionRow, sid).media_deleted_at is None
        key = db.get(SessionKeyRow, sid)
        if private:
            assert key.wrapped_key is None and key.destroyed_at is not None
        else:
            assert key is None
        audit = db.scalar(select(CleanupAuditRow).order_by(CleanupAuditRow.id.desc()).limit(1))
        assert audit.files == [] and audit.details["deleted"] == []
        assert audit.details["errors"]
        assert audit.details["session_erasure"] == [
            {
                "session_id": sid,
                "key_erasure": "destroyed" if private else "not_applicable",
                "files_erasure": "pending",
            }
        ]

    assert len(storage.cleanup_expired(root.database, root.settings, now=expiry)) == 1
    assert not folder.exists()
    with root.database.sessions() as db:
        assert db.get(SessionRow, sid).media_deleted_at is not None
        audit = db.scalar(select(CleanupAuditRow).order_by(CleanupAuditRow.id.desc()).limit(1))
        assert audit.details["session_erasure"][0]["files_erasure"] == "deleted"


def test_failed_cleanup_commit_does_not_claim_durable_key_erasure(
    private_client, monkeypatch, caplog
):
    client = private_client
    root = client.app.state.vericlue
    created, _ = start_session(client)
    sid = created["session_id"]
    with root.database.sessions() as db:
        original = db.get(SessionKeyRow, sid).wrapped_key

    def fail_commit(*_args):
        raise OperationalError("COMMIT", {}, RuntimeError("Synthetic commit failure"))

    with monkeypatch.context() as patch:
        patch.setattr(root.database.engine.dialect, "do_commit", fail_commit)
        with pytest.raises(OperationalError):
            storage.cleanup_expired(root.database, root.settings, now=utcnow() + timedelta(days=2))
    with root.database.sessions() as db:
        key = db.get(SessionKeyRow, sid)
        assert key.wrapped_key == original and key.destroyed_at is None
    messages = [r.message for r in caplog.records if r.message.startswith("media_cleanup_audit ")]
    audit = json.loads(messages[-1].removeprefix("media_cleanup_audit "))
    assert audit["transaction_committed"] is False
    assert audit["session_erasure"] == []
