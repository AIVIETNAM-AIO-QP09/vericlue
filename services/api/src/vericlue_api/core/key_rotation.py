"""Offline operator helpers: rewrap DEKs atomically, never decrypt media/identity."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from sqlalchemy import select, text

from vericlue_api.db.database import Database
from vericlue_api.db.models import AccountRow, SessionKeyRow
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.session_privacy import SessionPrivacy


class KeyRotationError(Exception):
    """Only a stable safe code may cross the CLI boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def fingerprint(key: bytes) -> str:
    """Public operator comparison label, not key discovery or identity proof."""
    return hashlib.sha256(b"vericlue-master-key-fingerprint-v1\0" + key).hexdigest()


def rewrap_master_keys(
    database: Database,
    old_master: bytes,
    new_master: bytes,
    *,
    apply: bool = False,
    services_stopped: bool = False,
) -> dict:
    """Verify all live envelopes; apply changes in one transaction or change none.

    The caller must stop services and protect backups. The acknowledgment is not
    proof that another process is stopped; locks cover only this transaction.
    """
    if not isinstance(old_master, bytes) or not isinstance(new_master, bytes):
        raise KeyRotationError("master_key_invalid")
    if len(old_master) != 32 or len(new_master) != 32:
        raise KeyRotationError("master_key_invalid")
    if old_master == new_master:
        raise KeyRotationError("master_keys_equal")
    if apply and not services_stopped:
        raise KeyRotationError("services_stopped_confirmation_required")
    counts = {
        "session_keys": 0,
        "account_keys": 0,
        "destroyed_session_keys": 0,
        "destroyed_account_keys": 0,
    }
    try:
        with database.sessions.begin() as db:
            dialect = db.bind.dialect.name
            if dialect not in {"sqlite", "postgresql"}:
                raise KeyRotationError("database_backend_unsupported")
            if apply:
                if dialect == "sqlite":
                    db.execute(text("BEGIN IMMEDIATE"))
                else:
                    db.execute(text("SET LOCAL lock_timeout = '5s'"))
                    db.execute(text("LOCK TABLE session_keys, accounts IN EXCLUSIVE MODE"))
            elif dialect == "postgresql":
                db.execute(text("SET TRANSACTION READ ONLY"))
            for row in db.scalars(select(SessionKeyRow).order_by(SessionKeyRow.session_id)):
                if row.destroyed_at is not None:
                    if row.wrapped_key is not None:
                        raise KeyRotationError("key_state_invalid")
                    counts["destroyed_session_keys"] += 1
                    continue
                if not row.wrapped_key:
                    raise KeyRotationError("key_state_invalid")
                aad = SessionPrivacy._aad(row.session_id, "dek")
                dek = SessionPrivacy._open(
                    old_master, base64.b64decode(row.wrapped_key, validate=True), aad
                )
                if len(dek) != 32:
                    raise KeyRotationError("dek_invalid")
                if apply:
                    row.wrapped_key = base64.b64encode(
                        SessionPrivacy._seal(new_master, dek, aad)
                    ).decode("ascii")
                del dek
                counts["session_keys"] += 1
            for row in db.scalars(select(AccountRow).order_by(AccountRow.account_id)):
                if row.destroyed_at is not None:
                    if row.wrapped_key is not None or row.encrypted_payload is not None:
                        raise KeyRotationError("key_state_invalid")
                    counts["destroyed_account_keys"] += 1
                    continue
                if not row.wrapped_key or not row.encrypted_payload:
                    raise KeyRotationError("key_state_invalid")
                aad = AccountStore._aad(row, "dek")
                dek = AccountStore._open(old_master, row.wrapped_key, aad)
                if len(dek) != 32:
                    raise KeyRotationError("dek_invalid")
                if apply:
                    row.wrapped_key = AccountStore._seal(new_master, dek, aad)
                del dek
                counts["account_keys"] += 1
    except KeyRotationError:
        raise
    except InvalidTag:
        raise KeyRotationError("rotation_integrity_failed") from None
    except Exception:
        # No DB URL, query parameters, row identifiers, envelope or exception repr.
        raise KeyRotationError("rotation_failed") from None
    return {
        "status": "rewrapped" if apply else "dry_run_ok",
        "old_master_fingerprint": fingerprint(old_master),
        "new_master_fingerprint": fingerprint(new_master),
        "counts": counts,
        "services_stopped_acknowledged": services_stopped,
        "services_stopped_verified": False,
        "coverage": "existing_session_and_account_deks_only",
        "not_checked": [
            "media_payload_integrity",
            "legacy_plaintext",
            "backup_retention",
            "operator_config_update",
        ],
    }


def inventory_private_temp(media_dir: str | Path, *, max_entries: int = 10000) -> dict:
    """Count only configured _decoded candidates; never read contents or delete."""
    original = Path(media_dir)
    if not original.is_dir() or original.is_symlink() or original.is_junction():
        raise KeyRotationError("temp_path_invalid")
    root = original.resolve()
    decoded = root / "_decoded"
    if decoded.is_symlink() or decoded.is_junction() or decoded.resolve().parent != root:
        raise KeyRotationError("temp_path_invalid")
    if not decoded.exists():
        return {
            "present": False,
            "candidate_leases": 0,
            "files": 0,
            "logical_file_bytes": 0,
            "unrecognized_entries": 0,
            "active_state": "not_checked",
            "deleted": 0,
        }
    if not decoded.is_dir():
        raise KeyRotationError("temp_path_invalid")
    counts = {
        "present": True,
        "candidate_leases": 0,
        "files": 0,
        "logical_file_bytes": 0,
        "unrecognized_entries": 0,
        "active_state": "not_checked",
        "deleted": 0,
    }
    seen = 0
    pending = [(decoded, True)]
    try:
        while pending:
            directory, top = pending.pop()
            if (
                directory.is_symlink()
                or directory.is_junction()
                or not directory.resolve().is_relative_to(decoded)
            ):
                raise KeyRotationError("temp_path_invalid")
            with os.scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen > max_entries:
                        raise KeyRotationError("temp_inventory_limit")
                    path = Path(entry.path)
                    if (
                        entry.is_symlink()
                        or path.is_junction()
                        or not path.resolve().is_relative_to(decoded)
                    ):
                        raise KeyRotationError("temp_path_invalid")
                    if top:
                        if not entry.is_dir(follow_symlinks=False) or not entry.name.startswith(
                            "lease-"
                        ):
                            counts["unrecognized_entries"] += 1
                            continue
                        counts["candidate_leases"] += 1
                    if entry.is_dir(follow_symlinks=False):
                        pending.append((path, False))
                    elif entry.is_file(follow_symlinks=False):
                        counts["files"] += 1
                        counts["logical_file_bytes"] += entry.stat(follow_symlinks=False).st_size
                    else:
                        raise KeyRotationError("temp_path_invalid")
    except KeyRotationError:
        raise
    except OSError:
        raise KeyRotationError("temp_inventory_failed") from None
    return counts
