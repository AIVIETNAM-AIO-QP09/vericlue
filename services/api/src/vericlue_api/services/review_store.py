"""Ca duyệt bền vững; hồ sơ tách điểm AI và sự kiện chỉ ghi thêm."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

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
)
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.provisional_decision import FACE_MODULES, fused_prob
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
        )

    def ai_opinion(self, b: float) -> ReviewAiOpinion:
        p = fused_prob(self.results, FACE_MODULES)
        usable = all(r.is_usable for r in self.results.values())
        suggestion = "pass" if usable and p is not None and p < b else "review"
        return ReviewAiOpinion(
            case_id=self.case_id,
            suggestion=suggestion,
            modules=[r.to_contract() for r in self.results.values()],
        )


class ReviewStore:
    def __init__(self, db: DBSession) -> None:
        self.db = db
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
        self._loaded[case_id] = (record, row)
        return record

    @staticmethod
    def _record(row: ReviewCaseRow) -> CaseRecord:
        data = row.payload
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

    def list(self, status: CaseStatus | None, priority: Priority | None) -> list[CaseRecord]:
        # Listing is read-only: neither row locks nor entries in the writable cache.
        query = select(ReviewCaseRow)
        if status is not None:
            query = query.where(ReviewCaseRow.status == status)
        if priority is not None:
            query = query.where(ReviewCaseRow.priority == priority)
        items = [self._record(row) for row in self.db.scalars(query)]
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
                results=run_detectors(DEMO_MODULES, session_id=sid, scenario=scenario),
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
            row.payload = {
                "scenario": record.scenario,
                "results": {str(k): v.to_contract() for k, v in record.results.items()},
                "media": [m.model_dump(mode="json") for m in record.media],
                "notes": list(record.notes),
            }

    def record_event(
        self,
        record: CaseRecord,
        action: str,
        decision: str,
        *,
        reason_code: str | None = None,
        note: str | None = None,
    ) -> None:
        previous = (
            self.db.scalar(
                select(ReviewEventRow.hash)
                .where(ReviewEventRow.case_id == record.case_id)
                .order_by(ReviewEventRow.id.desc())
                .limit(1)
            )
            or "0" * 64
        )
        now = utcnow()
        payload = {
            "case_id": record.case_id,
            "actor": "staff-unverified",
            "action": action,
            "decision": decision,
            "reason_code": reason_code,
            "note": note,
            "created_at": now.isoformat(),
        }
        digest = hashlib.sha256(
            (
                previous
                + json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            ).encode()
        ).hexdigest()
        self.db.add(
            ReviewEventRow(
                case_id=record.case_id,
                action=action,
                reason_code=reason_code,
                note=note,
                prev_hash=previous,
                hash=digest,
                payload=payload,
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
