"""Cumulative per-session resource budget, persisted with the locked snapshot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vericlue_api.core.errors import ApiError

if TYPE_CHECKING:
    from vericlue_api.core.config import Settings
    from vericlue_api.services.session_store import Session


def reserve_media(session: Session, settings: Settings, accounted_bytes: int) -> None:
    """Charge original and stored/canonical bytes inside the request transaction."""
    limit = settings.max_session_media_mb * 1024 * 1024
    if accounted_bytes < 0 or session.uploaded_media_bytes + accounted_bytes > limit:
        raise ApiError(413, "session_media_quota_exceeded", "Dữ liệu vượt giới hạn của phiên.")
    session.uploaded_media_bytes += accounted_bytes
