"""Session-scoped consent ledger and cryptographic erasure; never account-wide deletion."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.session_tokens import token_digest
from vericlue_api.db.models import PrivacyEventRow, SessionRow, aware, utcnow
from vericlue_api.schemas.privacy import PrivacyConsentRequest, PrivacyState
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import Session, SessionStore
from vericlue_api.services.storage import _delete_folder, _folder

MAX_CONSENT_EVENTS = 8
ENDPOINT_CATEGORIES: dict[str, frozenset[str]] = {
    "send_otp": frozenset({"contact"}),
    "verify_otp": frozenset({"contact"}),
    "upload_id_card": frozenset({"id_document"}),
    "confirm_id_card": frozenset({"id_document"}),
    "upload_media": frozenset({"face_biometrics"}),
    "upload_signals": frozenset({"face_biometrics"}),
    "finalize": frozenset({"face_biometrics"}),
    "voice": frozenset({"face_biometrics", "voice_biometrics"}),
}


def unavailable() -> ApiError:
    return ApiError(503, "privacy_unavailable", "Chức năng riêng tư chưa sẵn sàng.")


def withdrawn() -> ApiError:
    return ApiError(410, "session_withdrawn", "Phiên đã dừng xử lý theo yêu cầu của bạn.")


def withdrawal_event(db: DBSession, session_id: str) -> PrivacyEventRow | None:
    return db.scalar(
        select(PrivacyEventRow).where(
            PrivacyEventRow.session_id == session_id, PrivacyEventRow.kind == "withdrawal"
        )
    )


def require_session_active(db: DBSession, session_id: str) -> None:
    """This tombstone is independent of DEKs and always applies, even when consent is optional."""
    if withdrawal_event(db, session_id) is not None:
        raise withdrawn()


def require_categories(db: DBSession, settings: Settings, session_id: str, endpoint: str) -> None:
    """Enforce current-version categories at collection and again at use time."""
    require_session_active(db, session_id)
    required = ENDPOINT_CATEGORIES.get(endpoint, frozenset())
    if not settings.require_privacy_consent or not required:
        return
    events = list(
        db.scalars(
            select(PrivacyEventRow).where(
                PrivacyEventRow.session_id == session_id,
                PrivacyEventRow.kind == "consent",
                PrivacyEventRow.policy_version == settings.privacy_policy_version,
            )
        )
    )
    now = utcnow()
    if any(aware(e.recorded_at) > now for e in events):
        raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")
    granted = {c for event in events for c in event.categories}
    if not required.issubset(granted):
        raise ApiError(
            409, "privacy_consent_required", "Vui lòng xem và đồng ý mục xử lý dữ liệu phù hợp."
        )


class PrivacyService:
    def __init__(self, settings: Settings, db: DBSession) -> None:
        self.settings, self.db = settings, db
        self.privacy = SessionPrivacy(settings, db)

    def lock(self, session_id: str) -> None:
        if (
            self.db.scalar(
                select(SessionRow).where(SessionRow.session_id == session_id).with_for_update()
            )
            is None
        ):
            raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")

    def authorize(self, session_id: str, token: str) -> Session | None:
        """Current source token, or only the last token captured at withdrawal after erasure."""
        event = withdrawal_event(self.db, session_id)
        now = utcnow()
        if event is not None:
            if (
                event.token_hash is None
                or event.token_expires_at is None
                or aware(event.recorded_at) > now
                or aware(event.token_expires_at) <= now
                or not secrets.compare_digest(event.token_hash, token_digest(token))
            ):
                raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")
            return None
        # Local import avoids a module import cycle with core session preflight.
        from vericlue_api.core.security import _current_session

        session = _current_session(SessionStore(self.db, privacy=self.privacy), session_id, token)
        if session.created_at is not None and aware(session.created_at) > now:
            raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")
        return session

    def _events(self, session_id: str) -> list[PrivacyEventRow]:
        return list(
            self.db.scalars(
                select(PrivacyEventRow)
                .where(PrivacyEventRow.session_id == session_id)
                .order_by(PrivacyEventRow.recorded_at, PrivacyEventRow.receipt_id)
            )
        )

    def state(self, session_id: str) -> PrivacyState:
        events = self._events(session_id)
        if any(aware(e.recorded_at) > utcnow() for e in events):
            raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")
        withdrawal = next((e for e in events if e.kind == "withdrawal"), None)
        policy = withdrawal.policy_version if withdrawal else self.settings.privacy_policy_version
        grants = [e for e in events if e.kind == "consent" and e.policy_version == policy]
        last = grants[-1] if grants else None
        categories = sorted({c for e in grants for c in e.categories})
        return PrivacyState(
            session_id=session_id,
            policy_version=policy,
            status="withdrawn" if withdrawal else "granted" if grants else "not_granted",
            categories=categories,
            consent_receipt_id=last.receipt_id if last else None,
            consented_at=aware(last.recorded_at) if last else None,
            withdrawal_receipt_id=withdrawal.receipt_id if withdrawal else None,
            withdrawn_at=aware(withdrawal.recorded_at) if withdrawal else None,
            storage_erasure=(
                "files_deleted"
                if any(e.kind == "files_erased" for e in events)
                else "key_destroyed"
            )
            if withdrawal
            else "not_requested",
            processing_cleanup="not_verified" if withdrawal else "not_applicable",
        )

    def grant(self, session_id: str, token: str, body: PrivacyConsentRequest) -> PrivacyState:
        self.lock(session_id)
        session = self.authorize(session_id, token)
        if session is None:
            raise withdrawn()
        if session.completed or session.case_id is not None:
            raise ApiError(409, "session_closed", "Phiên đã kết thúc. Vui lòng bắt đầu lại.")
        if body.policy_version != self.settings.privacy_policy_version:
            raise ApiError(
                409, "privacy_policy_changed", "Thông báo dữ liệu đã thay đổi. Vui lòng xem lại."
            )
        events = self._events(session_id)
        if any(aware(e.recorded_at) > utcnow() for e in events):
            raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")
        current = {
            c
            for e in events
            if e.kind == "consent" and e.policy_version == body.policy_version
            for c in e.categories
        }
        if set(body.categories).issubset(current):
            return self.state(session_id)
        if sum(e.kind == "consent" for e in events) >= MAX_CONSENT_EVENTS:
            raise ApiError(409, "privacy_receipt_limit", "Vui lòng bắt đầu phiên xác minh mới.")
        now = utcnow()
        if aware(session.token_expires_at) <= now:
            raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")
        self.db.add(
            PrivacyEventRow(
                receipt_id="prv_" + secrets.token_hex(16),
                session_id=session_id,
                kind="consent",
                policy_version=body.policy_version,
                categories=sorted(body.categories),
                recorded_at=now,
            )
        )
        self.db.flush()
        return self.state(session_id)

    def withdraw(self, session_id: str, token: str) -> None:
        self.lock(session_id)
        session = self.authorize(session_id, token)
        if session is None:
            return
        # Legacy/plaintext copies require a separate migration/deletion procedure.
        if not self.settings.session_privacy:
            raise unavailable()
        now = utcnow()
        if aware(session.token_expires_at) <= now:
            raise ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")
        self.db.add(
            PrivacyEventRow(
                receipt_id="prv_" + secrets.token_hex(16),
                session_id=session_id,
                kind="withdrawal",
                policy_version=self.settings.privacy_policy_version,
                categories=[],
                recorded_at=now,
                token_hash=token_digest(token),
                token_expires_at=session.token_expires_at,
            )
        )
        self.privacy.destroy(session_id)
        self.db.flush()


def erase_committed_session_files(root, session_id: str) -> None:
    """Best-effort after withdrawal commit; plaintext inference leases may finish later."""
    try:
        with root.database.sessions() as db:
            if withdrawal_event(db, session_id) is None:
                return
        media_root = Path(root.settings.media_dir).resolve()
        folder = _folder(root.settings.media_dir, session_id)
        _delete_folder(folder, media_root, lambda _: None)
        with root.database.sessions.begin() as db:
            row = db.scalar(
                select(SessionRow).where(SessionRow.session_id == session_id).with_for_update()
            )
            event = withdrawal_event(db, session_id)
            if row is None or event is None:
                return
            row.media_deleted_at = utcnow()
            prior = db.scalar(
                select(PrivacyEventRow.receipt_id).where(
                    PrivacyEventRow.session_id == session_id, PrivacyEventRow.kind == "files_erased"
                )
            )
            if prior is None:
                db.add(
                    PrivacyEventRow(
                        receipt_id="prv_" + secrets.token_hex(16),
                        session_id=session_id,
                        kind="files_erased",
                        policy_version=event.policy_version,
                        categories=[],
                        recorded_at=utcnow(),
                    )
                )
    except Exception:
        # Committed withdrawal stays authoritative even if filesystem or follow-up DB fails.
        logging.getLogger(__name__).warning("session_erasure_files_pending")
