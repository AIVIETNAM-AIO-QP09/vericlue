"""Lưu media ngoài DB; dọn theo TTL và audit mỗi lượt, giữ chứng cứ mặc định."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from vericlue_api.core.config import Settings
from vericlue_api.db.database import Database
from vericlue_api.db.models import CleanupAuditRow, ForensicJobRow, SessionRow, aware, utcnow

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


def save_upload(media_dir: str, folder: str, stem: str, filename: str | None, data: bytes) -> Path:
    """Giữ đuôi trong whitelist; tên gốc chỉ dùng như metadata, không làm đường dẫn."""
    suffix = Path(filename or "").suffix.lower()
    return save_generated(
        media_dir, folder, stem + (suffix if suffix in ALLOWED_SUFFIXES else ".bin"), data
    )


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
    try:
        with database.sessions.begin() as db:
            rows = db.scalars(
                select(SessionRow)
                .where(SessionRow.media_deleted_at.is_(None))
                .order_by(SessionRow.session_id)
                .with_for_update()
            )
            for row in rows:
                if row.ever_review:
                    base, ttl, reason = (
                        row.decided_at,
                        timedelta(days=settings.media_ttl_review_days),
                        "review_expired",
                    )
                elif row.status == "pass":
                    base, ttl, reason = (
                        row.decided_at,
                        timedelta(hours=settings.media_ttl_pass_hours),
                        "pass_expired",
                    )
                else:
                    base, ttl, reason = (
                        row.last_activity_at,
                        timedelta(hours=settings.media_ttl_incomplete_hours),
                        "incomplete_expired",
                    )
                if base is None or now < aware(base) + ttl:
                    continue
                try:
                    folder = _folder(settings.media_dir, row.session_id)
                    _delete_folder(
                        folder,
                        root,
                        lambda name, reason=reason: deleted.append(
                            {"path": name, "reason": reason}
                        ),
                    )
                    row.media_deleted_at = now
                except (OSError, ValueError) as exc:
                    errors.append({"id": row.session_id, "error": str(exc)})
            for job in db.scalars(
                select(ForensicJobRow)
                .where(ForensicJobRow.media_deleted_at.is_(None))
                .order_by(ForensicJobRow.job_id)
                .with_for_update()
            ):
                if settings.forensic_ttl_days is None:
                    protected.append(job.job_id)
                    continue
                if now < aware(job.created_at) + timedelta(days=settings.forensic_ttl_days):
                    continue
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
            details = {"deleted": deleted, "protected_forensic": protected, "errors": errors}
            db.add(
                CleanupAuditRow(
                    created_at=now,
                    files=[item["path"] for item in deleted],
                    reason="media_cleanup",
                    details=details,
                )
            )
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
                },
                ensure_ascii=False,
            ),
        )
    return deleted
