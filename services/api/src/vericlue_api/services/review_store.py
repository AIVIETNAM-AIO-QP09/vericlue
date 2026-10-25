"""Ca duyệt bền vững; hồ sơ tách điểm AI và sự kiện chỉ ghi thêm."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import (
    DecisionRow,
    ReviewCaseRow,
    ReviewEventRow,
    SessionRow,
    aware,
    utcnow,
)
from vericlue_api.schemas.review import (
    CaseStatus,
    Decision,
    MediaRef,
    Priority,
    ReviewAiOpinion,
    ReviewCase,
    ReviewCaseSummary,
    ReviewEvent,
)
from vericlue_api.services.audit_log import (
    GENESIS_HASH,
    ChainCheck,
    ChainEvent,
    compute_hash,
    verify_chain,
)
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.provisional_decision import FACE_MODULES, fused_prob
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_ml.common.result import Module, ModuleResult

DEMO_MODULES = (
    Module.QUALITY,
    Module.FACE_PAD,
    Module.FACE_DEEPFAKE,
    Module.CHROMAPULSE,
    Module.CAMPROBE,
)


@dataclass
class CaseRecord:
    case_id: str
    session_id: str
    priority: Priority
    scenario: str
    results: dict[Module, ModuleResult]
    media: list[MediaRef]
    notes: list[str] = field(default_factory=list)
    status: CaseStatus = "open"
    initial_decision: Decision | None = None
    final_decision: Decision | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    history: list[ReviewEvent] = field(default_factory=list)

    def summary(self) -> ReviewCaseSummary:
        return ReviewCaseSummary(
            case_id=self.case_id,
            session_id=self.session_id,
            status=self.status,
            priority=self.priority,
            created_at=self.created_at,
        )

    def to_case(self) -> ReviewCase:
        """Hồ sơ cho nhân viên: KHÔNG có điểm AI."""
        return ReviewCase(
            **self.summary().model_dump(),
            media=self.media,
            capture_notes=self.notes,
            initial_decision=self.initial_decision,
            final_decision=self.final_decision,
            history=self.history,
        )

    def ai_opinion(self, b: float) -> ReviewAiOpinion:
        p = fused_prob(self.results, FACE_MODULES)
        usable = all(r.is_usable for r in self.results.values())
        suggestion = "pass" if usable and p is not None and p <= b else "review"
        return ReviewAiOpinion(
            case_id=self.case_id,
            suggestion=suggestion,
            modules=[r.to_contract() for r in self.results.values()],
        )


class ReviewStore:
    def __init__(
        self,
        db: DBSession,
        *,
        runner: Callable = run_detectors,
        privacy: SessionPrivacy | None = None,
    ) -> None:
        self.db = db
        self._run = runner
        self.privacy = privacy
        self.actor = "staff-unverified"
        self._loaded: dict[str, tuple[CaseRecord, ReviewCaseRow]] = {}

    def add(
        self,
        *,
        session_id: str,
        priority: Priority,
        scenario: str,
        results: dict[Module, ModuleResult],
        media: list[MediaRef],
        notes: list[str] | None = None,
    ) -> CaseRecord:
        record = CaseRecord(
            case_id=f"case_{secrets.token_hex(6)}",
            session_id=session_id,
            priority=priority,
            scenario=scenario,
            results=results,
            media=media,
            notes=notes or [],
        )
        row = ReviewCaseRow(
            case_id=record.case_id,
            session_id=session_id,
            priority=priority,
            created_at=record.created_at,
        )
        self.db.add(row)
        self.db.flush()
        self._loaded[record.case_id] = (record, row)
        return record

    def get(self, case_id: str) -> CaseRecord | None:
        if case_id in self._loaded:
            return self._loaded[case_id][0]
        row = self.db.scalar(
            select(ReviewCaseRow).where(ReviewCaseRow.case_id == case_id).with_for_update()
        )
        if row is None:
            return None
        record = self._record(row)
        record.history = self._history(case_id, record.session_id)
        self._loaded[case_id] = (record, row)
        return record

    def get_metadata(self, case_id: str) -> CaseRecord | None:
        """Audit verification must remain possible after the content key expires."""
        row = self.db.scalar(
            select(ReviewCaseRow).where(ReviewCaseRow.case_id == case_id).with_for_update()
        )
        return self._metadata(row) if row is not None else None

    @staticmethod
    def _metadata(row: ReviewCaseRow) -> CaseRecord:
        return CaseRecord(
            case_id=row.case_id,
            session_id=row.session_id,
            priority=row.priority,
            status=row.status,
            scenario="",
            results={},
            media=[],
            created_at=aware(row.created_at),
            initial_decision=row.initial_decision,
            final_decision=row.final_decision,
        )

    def _record(self, row: ReviewCaseRow) -> CaseRecord:
        data = (
            self.privacy.open_json(row.session_id, "review:" + row.case_id, row.payload)
            if self.privacy
            else row.payload
        )
        return CaseRecord(
            case_id=row.case_id,
            session_id=row.session_id,
            priority=row.priority,
            status=row.status,
            scenario=data["scenario"],
            created_at=aware(row.created_at),
            results={Module(k): ModuleResult.model_validate(v) for k, v in data["results"].items()},
            media=[MediaRef.model_validate(m) for m in data["media"]],
            notes=data["notes"],
            initial_decision=row.initial_decision,
            final_decision=row.final_decision,
        )

    def _events(self, case_id: str) -> list[ReviewEventRow]:
        return list(
            self.db.scalars(
                select(ReviewEventRow)
                .where(ReviewEventRow.case_id == case_id)
                .order_by(ReviewEventRow.id)
            )
        )

    def _history(self, case_id: str, session_id: str) -> list[ReviewEvent]:
        return [
            ReviewEvent(
                action=e.action,
                decision=e.payload["decision"],
                reason_code=e.reason_code,
                note=(
                    self.privacy.open_json(
                        session_id, "review-note:" + case_id, e.payload["private_note"]
                    ).get("note")
                    if self.privacy and "private_note" in e.payload
                    else e.note
                ),
                actor=e.actor,
                created_at=aware(e.created_at),
            )
            for e in self._events(case_id)
        ]

    def verify(self, case_id: str) -> ChainCheck:
        """Rehash payload ĐÃ LƯU của mọi sự kiện trong ca."""
        return verify_chain(
            [ChainEvent(e.prev_hash, e.hash, e.payload) for e in self._events(case_id)]
        )

    def list(self, status: CaseStatus | None, priority: Priority | None) -> list[CaseRecord]:
        # Listing is read-only: neither row locks nor entries in the writable cache.
        query = select(ReviewCaseRow)
        if status is not None:
            query = query.where(ReviewCaseRow.status == status)
        if priority is not None:
            query = query.where(ReviewCaseRow.priority == priority)
        items = [
            self._metadata(row) if self.privacy and self.privacy.enabled else self._record(row)
            for row in self.db.scalars(query)
        ]
        return sorted(items, key=lambda c: (c.priority != "high", -c.created_at.timestamp()))

    def seed_demo(self) -> None:
        """Hai ca mẫu để bàn duyệt có dữ liệu ngay khi chạy mock."""
        if self.db.bind.dialect.name == "postgresql":
            # Serialize demo seeding across concurrent API workers, not just within one process.
            key = int.from_bytes(hashlib.sha256(b"vericlue-demo-seed").digest()[:8], signed=True)
            self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        demo: tuple[tuple[str, Priority, str], ...] = (
            ("virtual_cam", "high", "Phòng đủ sáng, camera ngoài"),
            ("print", "normal", "Chụp ngược sáng"),
        )
        for scenario, priority, note in demo:
            sid = f"ses_demo_{scenario}"
            if self.db.scalar(select(ReviewCaseRow.case_id).where(ReviewCaseRow.session_id == sid)):
                continue
            if self.db.get(SessionRow, sid) is None:
                self.db.add(SessionRow(session_id=sid, status="review", ever_review=True))
                self.db.flush()
            self.add(
                session_id=sid,
                priority=priority,
                scenario=scenario,
                results=self._run(DEMO_MODULES, session_id=sid, scenario=scenario),
                media=[
                    MediaRef(kind="face_image", url=f"/media/{sid}/face_image"),
                    MediaRef(kind="face_video", url=f"/media/{sid}/face_video"),
                ],
                notes=[note],
            )

    def save_all(self) -> None:
        for record, row in self._loaded.values():
            row.status = record.status
            row.priority = record.priority
            row.initial_decision = record.initial_decision
            row.final_decision = record.final_decision
            payload = {
                "scenario": record.scenario,
                "results": {str(k): v.to_contract() for k, v in record.results.items()},
                "media": [m.model_dump(mode="json") for m in record.media],
                "notes": list(record.notes),
            }
            row.payload = (
                self.privacy.seal_json(record.session_id, "review:" + record.case_id, payload)
                if self.privacy
                else payload
            )

    def _claim_decision(self, record: CaseRecord, action: str, decision: str) -> None:
        """Atomically reserve this transition before reading/appending the audit chain."""
        statement = update(ReviewCaseRow).where(
            ReviewCaseRow.case_id == record.case_id,
            ReviewCaseRow.final_decision.is_(None),
        )
        if action == "initial":
            statement = statement.where(
                ReviewCaseRow.status == "open", ReviewCaseRow.initial_decision.is_(None)
            ).values(initial_decision=decision, status="initial_decided")
        elif action == "final":
            statement = statement.where(
                ReviewCaseRow.status == "initial_decided",
                ReviewCaseRow.initial_decision.is_not(None),
                ReviewCaseRow.initial_decision == record.initial_decision,
            ).values(final_decision=decision, status="closed")
        else:
            raise ValueError("Unknown review transition")
        # SQLite ignores SELECT FOR UPDATE. Chain uniqueness alone does not stop
        # a stale request appending a second decision to the winner's new chain tip.
        result = self.db.execute(statement.execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise ApiError(
                409, "review_conflict", "Ca vừa được người khác cập nhật. Hãy tải lại và thử lại."
            )

    def record_event(
        self,
        record: CaseRecord,
        action: str,
        decision: str,
        *,
        reason_code: str | None = None,
        note: str | None = None,
    ) -> None:
        self._claim_decision(record, action, decision)
        previous = (
            self.db.scalar(
                select(ReviewEventRow.hash)
                .where(ReviewEventRow.case_id == record.case_id)
                .order_by(ReviewEventRow.id.desc())
                .limit(1)
            )
            or GENESIS_HASH
        )
        now = utcnow()
        payload = {
            "case_id": record.case_id,
            "actor": self.actor,
            "action": action,
            "decision": decision,
            "reason_code": reason_code,
            "note": note,
            "created_at": now.isoformat(),
        }
        encrypted_note = bool(self.privacy and self.privacy.enabled and note is not None)
        if encrypted_note:
            payload["note"] = None
            payload["private_note"] = self.privacy.seal_json(
                record.session_id, "review-note:" + record.case_id, {"note": note}
            )
        digest = compute_hash(previous, payload)
        self.db.add(
            ReviewEventRow(
                case_id=record.case_id,
                action=action,
                reason_code=reason_code,
                note=None if encrypted_note else note,
                actor=self.actor,
                prev_hash=previous,
                hash=digest,
                payload=payload,
                created_at=now,
            )
        )
        try:
            # Flush ngay để vi phạm UNIQUE(case_id, prev_hash) thành 409 chứ không phải 500.
            self.db.flush()
        except IntegrityError as exc:
            raise ApiError(
                409, "review_conflict", "Ca vừa được người khác cập nhật. Hãy tải lại và thử lại."
            ) from exc
        record.history.append(
            ReviewEvent(
                action=action,  # type: ignore[arg-type]
                decision=decision,  # type: ignore[arg-type]
                reason_code=reason_code,
                note=note,
                actor=self.actor,
                created_at=now,
            )
        )
        if action == "final":
            row = self.db.scalar(
                select(SessionRow)
                .where(SessionRow.session_id == record.session_id)
                .with_for_update()
            )
            row.ever_review = True
            row.decided_at = now
            row.status = "review"
            self.db.add(
                DecisionRow(
                    session_id=record.session_id,
                    action=decision,
                    config_version="staff-unverified@PLAT-04",
                )
            )
