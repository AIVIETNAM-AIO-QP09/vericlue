"""SEC-08 isolated envelope rotation with synthetic payloads and real AES-GCM."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr
from sqlalchemy import event, select

from vericlue_api.core.config import Settings
from vericlue_api.core.key_rotation import (
    KeyRotationError,
    inventory_private_temp,
    rewrap_master_keys,
)
from vericlue_api.db.database import Database
from vericlue_api.db.models import AccountRow, SessionKeyRow, SessionRow, utcnow
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.session_privacy import SessionPrivacy


@pytest.fixture
def vault():
    database = Database(os.environ["DATABASE_URL"])
    old, new = secrets.token_bytes(32), secrets.token_bytes(32)
    settings = Settings(
        _env_file=None, session_privacy=True, session_master_key=base64.b64encode(old).decode()
    )
    with database.sessions.begin() as db:
        row = SessionRow(session_id="ses_synthetic", payload={})
        db.add(row)
        db.flush()
        privacy = SessionPrivacy(settings, db)
        row.payload = privacy.seal_json(row.session_id, "session", {"synthetic": "unchanged"})
        account = AccountRow(
            account_id="acct_synthetic",
            source_session_id=row.session_id,
            id_number_hmac="a" * 64,
            phone_hmac="b" * 64,
            device_id="dev_synthetic",
            created_at=utcnow(),
            expires_at=utcnow() + timedelta(hours=24),
        )
        db.add(account)
        db.flush()
        key = AESGCM.generate_key(bit_length=256)
        account.wrapped_key = AccountStore._seal(old, key, AccountStore._aad(account, "dek"))
        account.encrypted_payload = AccountStore._seal(
            key, b'{"synthetic":true}', AccountStore._aad(account, "identity")
        )
        tombstone = SessionRow(session_id="ses_destroyed", payload={})
        db.add(tombstone)
        db.flush()
        db.add(
            SessionKeyRow(session_id=tombstone.session_id, destroyed_at=utcnow(), wrapped_key=None)
        )
    yield database, old, new, settings
    database.dispose()


def envelopes(database):
    with database.sessions() as db:
        return (
            [
                (r.session_id, r.wrapped_key, r.destroyed_at)
                for r in db.scalars(select(SessionKeyRow).order_by(SessionKeyRow.session_id))
            ],
            [
                (r.account_id, r.wrapped_key, r.encrypted_payload)
                for r in db.scalars(select(AccountRow).order_by(AccountRow.account_id))
            ],
        )


def test_dry_run_verifies_without_changing_rows_or_database_file(vault):
    database, old, new, _ = vault
    before = envelopes(database)
    path = Path(database.engine.url.database)
    digest = hashlib.sha256(path.read_bytes()).digest()
    report = rewrap_master_keys(database, old, new)
    assert report["status"] == "dry_run_ok"
    assert report["counts"] == {
        "session_keys": 1,
        "account_keys": 1,
        "destroyed_session_keys": 1,
        "destroyed_account_keys": 0,
    }
    assert report["services_stopped_verified"] is False
    assert envelopes(database) == before
    assert hashlib.sha256(path.read_bytes()).digest() == digest


def test_apply_uses_new_master_with_unchanged_payloads(vault):
    database, old, new, settings = vault
    before = envelopes(database)
    report = rewrap_master_keys(database, old, new, apply=True, services_stopped=True)
    assert report["status"] == "rewrapped"
    after = envelopes(database)
    assert before[0] != after[0] and before[1][0][1] != after[1][0][1]
    assert before[1][0][2] == after[1][0][2]
    current = settings.model_copy(
        update={"session_master_key": SecretStr(base64.b64encode(new).decode())}
    )
    with database.sessions() as db:
        row = db.get(SessionRow, "ses_synthetic")
        assert SessionPrivacy(current, db).open_json(row.session_id, "session", row.payload) == {
            "synthetic": "unchanged"
        }
        account = db.get(AccountRow, "acct_synthetic")
        key = AccountStore._open(new, account.wrapped_key, AccountStore._aad(account, "dek"))
        assert (
            AccountStore._open(
                key, account.encrypted_payload, AccountStore._aad(account, "identity")
            )
            == b'{"synthetic":true}'
        )
        with pytest.raises(InvalidTag):
            AccountStore._open(old, account.wrapped_key, AccountStore._aad(account, "dek"))
        assert db.get(SessionKeyRow, "ses_destroyed").wrapped_key is None


def test_missing_ack_cannot_touch_database(vault):
    database, old, new, _ = vault
    before = envelopes(database)
    with pytest.raises(KeyRotationError, match="services_stopped_confirmation_required"):
        rewrap_master_keys(database, old, new, apply=True)
    assert envelopes(database) == before


def test_wrong_old_master_changes_nothing(vault):
    database, _, new, _ = vault
    before = envelopes(database)
    with pytest.raises(KeyRotationError, match="rotation_integrity_failed"):
        rewrap_master_keys(
            database, secrets.token_bytes(32), new, apply=True, services_stopped=True
        )
    assert envelopes(database) == before


def test_corrupt_later_account_rolls_back_already_rewrapped_sessions(vault):
    database, old, new, _ = vault
    with database.sessions.begin() as db:
        row = db.get(AccountRow, "acct_synthetic")
        raw = bytearray(base64.b64decode(row.wrapped_key))
        raw[-1] ^= 1
        row.wrapped_key = base64.b64encode(raw).decode()
    before = envelopes(database)
    with pytest.raises(KeyRotationError, match="rotation_integrity_failed"):
        rewrap_master_keys(database, old, new, apply=True, services_stopped=True)
    assert envelopes(database) == before


def test_commit_failure_rolls_back_all_envelopes(vault):
    database, old, new, _ = vault
    before = envelopes(database)

    def fail(db):
        raise RuntimeError("synthetic failure; must never cross CLI boundary")

    event.listen(database.sessions, "before_commit", fail)
    try:
        with pytest.raises(KeyRotationError, match="rotation_failed"):
            rewrap_master_keys(database, old, new, apply=True, services_stopped=True)
    finally:
        event.remove(database.sessions, "before_commit", fail)
    assert envelopes(database) == before


def test_destroyed_accounts_stay_destroyed_and_invalid_tombstones_fail_closed(vault):
    database, old, new, _ = vault
    with database.sessions.begin() as db:
        row = db.get(AccountRow, "acct_synthetic")
        row.destroyed_at = utcnow()
        row.wrapped_key = row.encrypted_payload = None
    report = rewrap_master_keys(database, old, new, apply=True, services_stopped=True)
    assert report["counts"]["destroyed_account_keys"] == 1
    assert envelopes(database)[1][0][1:] == (None, None)
    with database.sessions.begin() as db:
        db.get(SessionKeyRow, "ses_destroyed").wrapped_key = "invalid-resurrected-key"
    before = envelopes(database)
    with pytest.raises(KeyRotationError, match="key_state_invalid"):
        rewrap_master_keys(database, new, old, apply=True, services_stopped=True)
    assert envelopes(database) == before


def test_invalid_or_reused_keys_are_rejected_before_queries(vault):
    database, old, new, _ = vault
    for bad in [b"short", "not bytes"]:
        with pytest.raises(KeyRotationError, match="master_key_invalid"):
            rewrap_master_keys(database, bad, new)
    with pytest.raises(KeyRotationError, match="master_keys_equal"):
        rewrap_master_keys(database, old, old)


def run_cli(tmp_path, args):
    root = Path(__file__).parents[3]
    return subprocess.run(
        [sys.executable, str(root / "scripts/rotate_master_keys.py"), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_cli_dry_run_and_apply_hide_keys_paths_and_database_url(vault, tmp_path, monkeypatch):
    database, old, new, _ = vault
    oldfile, newfile = tmp_path / "PRIVATE_old.key", tmp_path / "PRIVATE_new.key"
    oldfile.write_text(base64.b64encode(old).decode(), encoding="ascii")
    newfile.write_text(base64.b64encode(new).decode(), encoding="ascii")
    monkeypatch.setenv("ROTATION_DB", str(database.engine.url))
    args = [
        "--database-env",
        "ROTATION_DB",
        "--old-master-file",
        str(oldfile),
        "--new-master-file",
        str(newfile),
    ]
    before = envelopes(database)
    dry = run_cli(tmp_path, args)
    assert dry.returncode == 0, dry.stderr + dry.stdout
    assert json.loads(dry.stdout)["status"] == "dry_run_ok"
    assert envelopes(database) == before
    applied = run_cli(tmp_path, [*args, "--apply", "--confirm-services-stopped"])
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert json.loads(applied.stdout)["status"] == "rewrapped"
    for result in [dry, applied]:
        for secret in [
            str(oldfile),
            str(newfile),
            str(database.engine.url),
            base64.b64encode(old).decode(),
            base64.b64encode(new).decode(),
        ]:
            assert secret not in result.stdout + result.stderr


def test_cli_refuses_missing_ack_and_inline_secrets_without_echo(tmp_path, monkeypatch):
    args = [
        "--database-env",
        "UNSET_DB",
        "--old-master-env",
        "UNSET_OLD",
        "--new-master-env",
        "UNSET_NEW",
        "--apply",
    ]
    result = run_cli(tmp_path, args)
    assert result.returncode == 2
    assert json.loads(result.stdout)["error_code"] == "services_stopped_confirmation_required"
    result = run_cli(tmp_path, [*args, "--old-master-key", "INLINE-SENSITIVE-VALUE"])
    assert result.returncode == 2
    assert "INLINE-SENSITIVE-VALUE" not in result.stdout + result.stderr


def test_cli_missing_database_does_not_create_a_file(tmp_path, monkeypatch):
    missing = tmp_path / "missing.sqlite"
    monkeypatch.setenv("ROTATION_DB", "sqlite:///" + missing.as_posix())
    monkeypatch.setenv("ROTATION_OLD", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("ROTATION_NEW", base64.b64encode(secrets.token_bytes(32)).decode())
    result = run_cli(
        tmp_path,
        [
            "--database-env",
            "ROTATION_DB",
            "--old-master-env",
            "ROTATION_OLD",
            "--new-master-env",
            "ROTATION_NEW",
        ],
    )
    assert result.returncode == 2
    assert not missing.exists()


def test_cli_refuses_live_sqlite_sidecars_and_invalid_keys_without_output_leaks(
    vault, tmp_path, monkeypatch
):
    database, old, new, _ = vault
    monkeypatch.setenv("ROTATION_DB", str(database.engine.url))
    monkeypatch.setenv("ROTATION_OLD", base64.b64encode(old).decode())
    monkeypatch.setenv("ROTATION_NEW", base64.b64encode(new).decode())
    args = [
        "--database-env",
        "ROTATION_DB",
        "--old-master-env",
        "ROTATION_OLD",
        "--new-master-env",
        "ROTATION_NEW",
    ]
    before = envelopes(database)
    sidecar = Path(str(database.engine.url.database) + "-wal")
    sidecar.write_bytes(b"synthetic-uncheckpointed-state")
    result = run_cli(tmp_path, args)
    assert result.returncode == 2
    assert "synthetic-uncheckpointed-state" not in result.stdout + result.stderr
    assert sidecar.read_bytes() == b"synthetic-uncheckpointed-state"
    sidecar.unlink()
    assert envelopes(database) == before
    monkeypatch.setenv("ROTATION_OLD", "SENSITIVE-invalid-base64")
    result = run_cli(tmp_path, args)
    assert result.returncode == 2
    assert "SENSITIVE-invalid-base64" not in result.stdout + result.stderr
    assert envelopes(database) == before


def test_temp_inventory_is_read_only_and_not_an_active_lease_detector(tmp_path):
    media = tmp_path / "media"
    lease = media / "_decoded" / "lease-synthetic"
    lease.mkdir(parents=True)
    target = lease / "0.jpg"
    target.write_bytes(b"synthetic-private-bytes")
    before = target.read_bytes()
    report = inventory_private_temp(media)
    assert report["candidate_leases"] == 1 and report["files"] == 1 and report["deleted"] == 0
    assert report["active_state"] == "not_checked"
    assert target.read_bytes() == before
    assert "synthetic-private-bytes" not in json.dumps(report)


def test_temp_inventory_rejects_symlink_without_following(tmp_path):
    media = tmp_path / "media"
    decoded = media / "_decoded"
    decoded.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (decoded / "lease-outside").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host cannot create symlinks; junction checks remain in implementation")
    with pytest.raises(KeyRotationError, match="temp_path_invalid"):
        inventory_private_temp(media)


def test_temp_inventory_bounds_walk_and_does_not_delete_unknown_entries(tmp_path):
    media = tmp_path / "media"
    decoded = media / "_decoded"
    decoded.mkdir(parents=True)
    note = decoded / "operator-note.txt"
    note.write_text("synthetic", encoding="ascii")
    assert inventory_private_temp(media)["unrecognized_entries"] == 1
    assert note.exists()
    with pytest.raises(KeyRotationError, match="temp_inventory_limit"):
        inventory_private_temp(media, max_entries=0)
