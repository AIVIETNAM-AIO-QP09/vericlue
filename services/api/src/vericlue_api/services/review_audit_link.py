"""Bind forensic material to owned media and verify a signed review-chain prefix."""

from __future__ import annotations

import hashlib
import stat
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import ForensicJobRow, ReviewCaseRow, ReviewEventRow, SessionRow, aware
from vericlue_api.schemas.forensic import (
    ForensicJob,
    ReviewAuditAnchor,
    ReviewAuditVerifyResponse,
)
from vericlue_api.services.audit_log import ChainEvent, verify_chain
from vericlue_api.services.session_privacy import SessionPrivacy

MAX_EVENTS = 4096
MAX_MEDIA_BYTES = 64 * 1024 * 1024
ROLES = {"face_video": "video", "voice_audio": "audio", "voice_video": "voice_video"}


def _case(db: DBSession, case_id: str) -> ReviewCaseRow | None:
    return db.scalar(
        select(ReviewCaseRow).where(ReviewCaseRow.case_id == case_id).with_for_update()
    )


def _events(db: DBSession, case_id: str) -> tuple[list[ReviewEventRow], bool]:
    rows = list(
        db.scalars(
            select(ReviewEventRow)
            .where(ReviewEventRow.case_id == case_id)
            .order_by(ReviewEventRow.id)
            .limit(MAX_EVENTS + 1)
        )
    )
    if len(rows) > MAX_EVENTS or any(
        not isinstance(r.payload, dict)
        or r.payload.get("case_id") != case_id
        or r.payload.get("action") != r.action
        or r.payload.get("actor") != r.actor
        or r.payload.get("reason_code") != r.reason_code
        or r.payload.get("note") != r.note
        for r in rows
    ):
        return rows, False
    try:
        if any(
            aware(r.created_at) != datetime.fromisoformat(r.payload["created_at"]) for r in rows
        ):
            return rows, False
        valid = verify_chain([ChainEvent(r.prev_hash, r.hash, r.payload) for r in rows]).ok
    except (KeyError, TypeError, ValueError):
        valid = False
    return rows, valid


def _consistent(case: ReviewCaseRow, rows: list[ReviewEventRow]) -> bool:
    """The current two-stage review protocol must agree with its recorded events."""
    if (
        not rows
        or rows[0].action != "initial"
        or case.initial_decision not in {"accept", "reject", "request_retry"}
    ):
        return False
    if rows[0].payload.get("decision") != case.initial_decision:
        return False
    if case.status == "initial_decided":
        return len(rows) == 1 and case.final_decision is None
    return (
        case.status == "closed"
        and len(rows) == 2
        and rows[1].action == "final"
        and case.final_decision in {"accept", "reject", "request_retry"}
        and rows[1].payload.get("decision") == case.final_decision
    )


def _inspect(
    anchor: ReviewAuditAnchor, case: ReviewCaseRow | None, rows, valid
) -> ReviewAuditVerifyResponse:
    def result(status, *, ok=False, current=None, appended=None):
        return ReviewAuditVerifyResponse(
            signature_valid=True,
            ok=ok,
            status=status,
            anchored_count=anchor.event_count,
            current_count=current,
            appended_count=appended,
        )

    if case is None or case.session_id != anchor.session_id:
        return result("case_unavailable")
    if not valid:
        return result("chain_invalid", current=len(rows))
    if len(rows) < anchor.event_count:
        return result("tail_truncated", current=len(rows))
    tail = rows[anchor.event_count - 1]
    if tail.id != anchor.tail_event_id or tail.hash != anchor.tail_hash:
        return result("anchor_mismatch", current=len(rows))
    if not _consistent(case, rows):
        return result("chain_invalid", current=len(rows))
    appended = len(rows) - anchor.event_count
    return result(
        "extended" if appended else "intact", ok=True, current=len(rows), appended=appended
    )


def check_review_anchor(db: DBSession, anchor: ReviewAuditAnchor) -> ReviewAuditVerifyResponse:
    """Only call with an anchor from a verified signature or the server's durable snapshot."""
    case = _case(db, anchor.case_id)
    rows, valid = _events(db, anchor.case_id) if case else ([], False)
    return _inspect(anchor, case, rows, valid)


class ReviewAuditLinker:
    def __init__(self, settings: Settings, db: DBSession, privacy: SessionPrivacy) -> None:
        self.settings, self.db, self.privacy = settings, db, privacy
        self.actor = "system-forensic-link"

    def bind(self, case_id: str, data: bytes) -> ReviewAuditAnchor:
        """Require initial human decision and exact byte equality to one server-owned role."""
        if not 0 < len(data) <= MAX_MEDIA_BYTES:
            raise ApiError(409, "linked_media_mismatch", "Không thể đối chiếu bản ghi với hồ sơ.")
        case = _case(self.db, case_id)
        if case is None:
            raise ApiError(404, "case_not_found", "Không tìm thấy hồ sơ cần liên kết.")
        if case.status not in {"initial_decided", "closed"} or case.initial_decision is None:
            raise ApiError(
                409,
                "review_link_not_ready",
                "Vui lòng ghi quyết định ban đầu trước khi liên kết giám định.",
            )
        rows, valid = _events(self.db, case_id)
        if not valid or not _consistent(case, rows):
            raise ApiError(409, "review_audit_invalid", "Nhật ký hồ sơ chưa thể xác minh.")
        session = self.db.scalar(
            select(SessionRow).where(SessionRow.session_id == case.session_id).with_for_update()
        )
        if session is None or session.media_deleted_at is not None:
            raise ApiError(410, "linked_media_unavailable", "Bản ghi của hồ sơ không còn sẵn sàng.")
        snapshot = self.privacy.open_json(case.session_id, "session", session.payload)
        digest = hashlib.sha256(data).hexdigest()
        expected = Path(self.settings.media_dir).resolve() / case.session_id
        if expected.parent != Path(self.settings.media_dir).resolve():
            raise ApiError(409, "linked_media_mismatch", "Không thể đối chiếu bản ghi với hồ sơ.")
        matched = None
        for role, field in ROLES.items():
            value = snapshot.get(field)
            if not isinstance(value, str) or not value:
                continue
            path = Path(value)
            try:
                info = path.stat(follow_symlinks=False)
                if (
                    path.is_symlink()
                    or path.parent.is_symlink()
                    or path.parent.is_junction()
                    or path.resolve().parent != expected
                    or not stat.S_ISREG(info.st_mode)
                    or not 0 < info.st_size <= MAX_MEDIA_BYTES + 32
                ):
                    continue
            except OSError:
                continue
            prepared, lease = self.privacy.prepare(case.session_id, {"video": path})
            try:
                total = 0
                hashed = hashlib.sha256()
                with prepared["video"].open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_MEDIA_BYTES:
                            break
                        hashed.update(chunk)
                if 0 < total <= MAX_MEDIA_BYTES and hashed.hexdigest() == digest:
                    matched = role
                    break
            finally:
                if lease is not None:
                    lease.release()
        if matched is None:
            raise ApiError(
                409, "linked_media_mismatch", "File tải lên không khớp bản ghi đang lưu của hồ sơ."
            )
        self.privacy.audit(case.session_id, actor=self.actor, action="forensic_source_link")
        return self._anchor(case, rows, matched, digest)

    @staticmethod
    def _anchor(case, rows, role, digest) -> ReviewAuditAnchor:
        return ReviewAuditAnchor(
            version=1,
            case_id=case.case_id,
            session_id=case.session_id,
            source_role=role,
            source_sha256=digest,
            captured_at=datetime.now(UTC),
            event_count=len(rows),
            tail_event_id=rows[-1].id,
            tail_hash=rows[-1].hash,
        )

    def refresh(self, job: ForensicJob, row: ForensicJobRow) -> ForensicJob:
        """Advance a checkpoint only after verifying its prefix; never silently re-anchor a cut tail."""
        anchor = job.review_audit
        if anchor is None:
            return job
        case = _case(self.db, anchor.case_id)
        rows, valid = _events(self.db, anchor.case_id) if case else ([], False)
        checked = _inspect(anchor, case, rows, valid)
        if not checked.ok:
            raise ApiError(
                409,
                "review_audit_invalid",
                "Nhật ký không còn khớp mốc đã lưu; chưa thể ký báo cáo mới.",
            )
        if checked.status == "intact":
            return job
        fresh = self._anchor(case, rows, anchor.source_role, anchor.source_sha256)
        updated = job.model_copy(update={"review_audit": fresh})
        payload = {**row.payload, "job": updated.model_dump(mode="json")}
        known = ForensicJobRow.payload["job"]["review_audit"]
        statement = (
            update(ForensicJobRow)
            .where(
                ForensicJobRow.job_id == job.job_id,
                ForensicJobRow.status == "done",
                ForensicJobRow.file_sha256 == job.file_sha256,
                ForensicJobRow.payload["mode"].as_string() == "real",
                known["case_id"].as_string() == anchor.case_id,
                known["session_id"].as_string() == anchor.session_id,
                known["source_role"].as_string() == anchor.source_role,
                known["source_sha256"].as_string() == anchor.source_sha256,
                known["event_count"].as_integer() == anchor.event_count,
                known["tail_hash"].as_string() == anchor.tail_hash,
                known["tail_event_id"].as_integer() == anchor.tail_event_id,
            )
            .values(payload=payload)
        )
        changed = self.db.execute(statement.execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise ApiError(409, "report_conflict", "Báo cáo vừa được cập nhật. Vui lòng thử lại.")
        self.db.expire(row, ["payload"])
        return updated
