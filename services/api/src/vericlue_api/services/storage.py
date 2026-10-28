"""Lưu media ngoài DB; dọn theo TTL và audit mỗi lượt, giữ chứng cứ mặc định."""

from __future__ import annotations

import json
import logging
import re
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, or_, select, text

from vericlue_api.core.config import Settings
from vericlue_api.core.retention import ekyc_expiry_filter
from vericlue_api.db.database import Database
from vericlue_api.db.models import (
    CleanupAuditRow,
    ForensicJobRow,
    ReviewCaseRow,
    SessionKeyRow,
    SessionRow,
    aware,
    utcnow,
)
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.file_changes import FileChanges
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.upload_images import PreparedImage, prepare_image

logger = logging.getLogger(__name__)
ALLOWED_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov", ".wav", ".mp3", ".m4a", ".ogg"}
)


def _folder(media_dir: str, folder: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?", folder):
        raise ValueError("Invalid media folder")
    root = Path(media_dir).resolve()
    target = root / folder
    # Refuse directory symlinks even if they currently resolve inside the store.
    current = target
    while current != root:
        if current.is_symlink() or current.is_junction():
            raise ValueError("Media folder cannot be a symlink")
        current = current.parent
    if not target.resolve().is_relative_to(root):
        raise ValueError("Media path escapes MEDIA_DIR")
    return target


def save_generated(media_dir: str, folder: str, name: str, data: bytes) -> Path:
    """Tên artifact nội bộ do server cấp; không dùng tên/path người gửi."""
    if Path(name).name != name or name in {".", ".."}:
        raise ValueError("Invalid media filename")
    target = _folder(media_dir, folder)
    target.mkdir(parents=True, exist_ok=True)
    path = target / name
    if path.is_symlink():
        raise ValueError("Media file cannot be a symlink")
    path.write_bytes(data)
    return path


def save_upload(
    media_dir: str,
    folder: str,
    stem: str,
    filename: str | None,
    data: bytes,
    *,
    privacy: SessionPrivacy | None = None,
    image_role: bool = False,
    prepared_image: PreparedImage | None = None,
    changes: FileChanges | None = None,
) -> Path:
    """Save server-named bytes; image roles use content validation in every mode."""
    suffix = Path(filename or "").suffix.lower()
    if image_role:
        prepared_image = prepared_image or prepare_image(data)
        data, suffix = prepared_image.data, prepared_image.suffix
    if changes is not None:
        stem += "_" + secrets.token_hex(16)
    name = stem + (suffix if suffix in ALLOWED_SUFFIXES else ".bin")
    if privacy is not None:
        data = privacy.seal_media(folder, name, data)
    if changes is not None:
        changes.track(_folder(media_dir, folder) / name)
    return save_generated(media_dir, folder, name, data)


def _delete_folder(folder: Path, root: Path, on_deleted: Callable[[str], None]) -> None:
    if (folder.is_symlink() or folder.is_junction()) or not folder.resolve().is_relative_to(root):
        raise ValueError("Refusing unsafe cleanup path")
    if not folder.exists():
        return
    entries = list(folder.rglob("*"))
    if any(
        (p.is_symlink() or p.is_junction()) or not p.resolve().is_relative_to(root) for p in entries
    ):
        raise ValueError("Refusing cleanup folder with symlink")
    for path in entries:
        if path.is_file():
            path.unlink()
            on_deleted(str(path))
    for path in sorted(
        (p for p in entries if p.is_dir()), key=lambda p: len(p.parts), reverse=True
    ):
        path.rmdir()
    folder.rmdir()


def cleanup_expired(
    database: Database, settings: Settings, *, now: datetime | None = None
) -> list[dict]:
    """Xóa file hết hạn; không xóa row kết quả/audit, ghi một audit row và một log line."""
    now = aware(now or utcnow())
    root = Path(settings.media_dir).resolve()
    deleted: list[dict] = []
    errors: list[dict] = []
    protected: list[str] = []
    session_erasure: list[dict] = []
    committed = False
    try:
        with database.sessions.begin() as db:
            if db.bind.dialect.name == "sqlite":
                # FOR UPDATE is ignored by SQLite. Take the write lock before
                # selecting rows or unlinking files, matching session uploads.
                db.execute(text("BEGIN IMMEDIATE"))
            has_review = (
                select(ReviewCaseRow.case_id)
                .where(ReviewCaseRow.session_id == SessionRow.session_id)
                .exists()
            )
            closed_review = (
                select(ReviewCaseRow.case_id)
                .where(
                    ReviewCaseRow.session_id == SessionRow.session_id,
                    ReviewCaseRow.status == "closed",
                )
                .exists()
            )
            never_reviewed = and_(SessionRow.ever_review.is_(False), ~has_review)
            expired = or_(
                and_(
                    never_reviewed,
                    SessionRow.status == "pass",
                    SessionRow.decided_at <= now - timedelta(hours=settings.media_ttl_pass_hours),
                ),
                and_(
                    SessionRow.ever_review.is_(True),
                    closed_review,
                    SessionRow.decided_at <= now - timedelta(days=settings.media_ttl_review_days),
                ),
                and_(
                    never_reviewed,
                    SessionRow.status.in_(("incomplete", "deny", "recovery_required")),
                    SessionRow.last_activity_at
                    <= now - timedelta(hours=settings.media_ttl_incomplete_hours),
                ),
            )
            if settings.product_mode == "ekyc":
                # No dependency on future staff UI or a manual case-close timestamp.
                expired = ekyc_expiry_filter(settings, now)
            rows = db.scalars(
                select(SessionRow)
                .where(SessionRow.media_deleted_at.is_(None), expired)
                .order_by(SessionRow.session_id)
                .with_for_update(skip_locked=True, of=SessionRow)
            )
            for row in rows:
                reason = (
                    "unverified_expired"
                    if settings.product_mode == "ekyc" and row.status != "pass"
                    else "review_expired"
                    if row.ever_review
                    else "pass_expired"
                    if row.status == "pass"
                    else "incomplete_expired"
                )
                privacy = SessionPrivacy(settings, db)
                key_erasure = "not_applicable"
                if settings.session_privacy:
                    # Key erasure must not depend on Windows handles/ACLs allowing
                    # physical unlink. Leave the media marker unset on file error
                    # so subsequent cleanup runs still retry the ciphertext files.
                    privacy.destroy(row.session_id)
                    key = db.get(SessionKeyRow, row.session_id)
                    key_erasure = (
                        "destroyed"
                        if key is not None and key.destroyed_at is not None
                        else "not_present"
                    )
                erasure = {
                    "session_id": row.session_id,
                    "key_erasure": key_erasure,
                    "files_erasure": "pending",
                }
                session_erasure.append(erasure)
                try:
                    folder = _folder(settings.media_dir, row.session_id)
                    _delete_folder(
                        folder,
                        root,
                        lambda name, reason=reason: deleted.append(
                            {"path": name, "reason": reason}
                        ),
                    )
                    if not settings.session_privacy:
                        # Preserve legacy cleanup of any older key after the
                        # plaintext files are removed; do not claim cryptoshred.
                        privacy.destroy(row.session_id)
                    row.media_deleted_at = now
                    erasure["files_erasure"] = "deleted"
                except (OSError, ValueError) as exc:
                    errors.append({"id": row.session_id, "error": str(exc)})
            if settings.forensic_ttl_days is None:
                # IDs only, without row locks: evidence retention is disabled by default.
                protected.extend(
                    db.scalars(
                        select(ForensicJobRow.job_id).where(
                            ForensicJobRow.media_deleted_at.is_(None)
                        )
                    )
                )
                jobs = []
            else:
                jobs = db.scalars(
                    select(ForensicJobRow)
                    .where(
                        ForensicJobRow.media_deleted_at.is_(None),
                        ForensicJobRow.created_at
                        <= now - timedelta(days=settings.forensic_ttl_days),
                    )
                    .order_by(ForensicJobRow.job_id)
                    .with_for_update(skip_locked=True)
                )
            for job in jobs:
                try:
                    folder = _folder(settings.media_dir, "forensic/" + job.job_id)
                    # Never follow an arbitrary persisted source_path outside this job folder.
                    for name in (job.source_path, job.report_path):
                        if name and not Path(name).resolve().is_relative_to(folder.resolve()):
                            raise ValueError("Forensic path is outside its evidence folder")
                    _delete_folder(
                        folder,
                        root,
                        lambda name: deleted.append({"path": name, "reason": "forensic_expired"}),
                    )
                    job.media_deleted_at = now
                except (OSError, ValueError) as exc:
                    errors.append({"id": job.job_id, "error": str(exc)})
            expired_accounts = AccountStore(settings, db).expire(now=now)
            details = {
                "deleted": deleted,
                "protected_forensic": protected,
                "errors": errors,
                "expired_accounts": expired_accounts,
                "session_erasure": session_erasure,
            }
            db.add(
                CleanupAuditRow(
                    created_at=now,
                    files=[item["path"] for item in deleted],
                    reason="media_cleanup",
                    details=details,
                )
            )
        committed = True
    except Exception as exc:
        errors.append({"id": "cleanup", "error": str(exc)})
        raise
    finally:
        # The log remains available even if the DB transaction cannot commit after unlink.
        logger.info(
            "media_cleanup_audit %s",
            json.dumps(
                {
                    "created_at": now.isoformat(),
                    "deleted": deleted,
                    "protected_forensic": protected,
                    "errors": errors,
                    # A rollback can undo key erasure, while physical unlinks
                    # above remain true. Never log an uncommitted key claim.
                    "transaction_committed": committed,
                    "session_erasure": session_erasure if committed else [],
                },
                ensure_ascii=False,
            ),
        )
    return deleted
