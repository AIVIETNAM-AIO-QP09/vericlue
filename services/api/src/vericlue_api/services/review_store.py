"""Kho ca duyệt trong bộ nhớ (TẠM — PLAT-05 thay bằng PostgreSQL; REV-01 thêm nhật ký băm)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime

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
    def __init__(self) -> None:
        self._cases: dict[str, CaseRecord] = {}

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
        self._cases[record.case_id] = record
        return record

    def get(self, case_id: str) -> CaseRecord | None:
        return self._cases.get(case_id)

    def list(self, status: CaseStatus | None, priority: Priority | None) -> list[CaseRecord]:
        items = [
            c
            for c in self._cases.values()
            if (status is None or c.status == status)
            and (priority is None or c.priority == priority)
        ]
        # ưu tiên cao lên trước, rồi mới nhất trước
        return sorted(items, key=lambda c: (c.priority != "high", -c.created_at.timestamp()))

    def seed_demo(self) -> None:
        """Hai ca mẫu để bàn duyệt có dữ liệu ngay khi chạy mock."""
        demo: tuple[tuple[str, Priority, str], ...] = (
            ("virtual_cam", "high", "Phòng đủ sáng, camera ngoài"),
            ("print", "normal", "Chụp ngược sáng"),
        )
        for scenario, priority, note in demo:
            sid = f"ses_demo_{scenario}"
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
