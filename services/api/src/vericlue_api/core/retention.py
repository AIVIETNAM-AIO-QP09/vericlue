"""Finite retention for eKYC-only sessions, independent of staff case closure."""

from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import SessionRow, aware, utcnow


def session_retention_deadline(settings: Settings, row: SessionRow) -> datetime | None:
    """Return the fixed deadline for the eKYC profile; tools retain their own policy."""
    if settings.product_mode != "ekyc":
        return None
    hours = (
        settings.media_ttl_pass_hours
        if row.status == "pass"
        else settings.media_ttl_unverified_hours
    )
    # Abandoned sessions cannot extend retention through polling/activity updates.
    anchor = (
        aware(row.decided_at)
        if row.decided_at is not None
        else aware(row.created_at) + timedelta(seconds=settings.session_max_seconds)
    )
    return anchor + timedelta(hours=hours)


def ensure_session_retained(
    settings: Settings, row: SessionRow, *, now: datetime | None = None
) -> None:
    """Deny access at the deadline even if physical cleanup has not run yet."""
    if settings.product_mode != "ekyc":
        return
    deadline = session_retention_deadline(settings, row)
    if row.media_deleted_at is not None or (
        deadline is not None and aware(now or utcnow()) >= deadline
    ):
        raise ApiError(410, "data_expired", "Dữ liệu phiên đã hết thời hạn lưu trữ.")


def ekyc_expiry_filter(settings: Settings, now: datetime) -> ColumnElement[bool]:
    """Build an equivalent DB predicate without decrypting session snapshots."""
    pass_cutoff = aware(now) - timedelta(hours=settings.media_ttl_pass_hours)
    unverified_cutoff = aware(now) - timedelta(hours=settings.media_ttl_unverified_hours)

    def before(cutoff: datetime) -> ColumnElement[bool]:
        return or_(
            and_(SessionRow.decided_at.is_not(None), SessionRow.decided_at <= cutoff),
            and_(
                SessionRow.decided_at.is_(None),
                SessionRow.created_at <= cutoff - timedelta(seconds=settings.session_max_seconds),
            ),
        )

    return or_(
        and_(SessionRow.status == "pass", before(pass_cutoff)),
        and_(SessionRow.status != "pass", before(unverified_cutoff)),
    )
