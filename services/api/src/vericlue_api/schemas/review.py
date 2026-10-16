"""Model Pydantic khớp `review.schema.json` (draft v1). ReviewCase KHÔNG có điểm AI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

CaseStatus = Literal["open", "initial_decided", "closed"]
Priority = Literal["normal", "high"]
Decision = Literal["accept", "reject", "request_retry"]


class MediaRef(BaseModel):
    kind: Literal["face_image", "face_video", "voice_audio"]
    url: str


class ReviewCaseSummary(BaseModel):
    case_id: str
    session_id: str
    status: CaseStatus
    priority: Priority
    created_at: datetime


class ReviewCaseList(BaseModel):
    items: list[ReviewCaseSummary]


class ReviewEvent(BaseModel):
    action: Literal["initial", "final"]
    decision: Decision
    reason_code: str | None = None
    note: str | None = None
    actor: str
    created_at: datetime


class ReviewCase(ReviewCaseSummary):
    media: list[MediaRef]
    capture_notes: list[str] = []
    initial_decision: Decision | None = None
    final_decision: Decision | None = None
    history: list[ReviewEvent] = []


class InitialDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Decision
    note: str | None = None


class ReviewAiOpinion(BaseModel):
    case_id: str
    suggestion: Literal["pass", "review", "retry"]
    modules: list[dict[str, Any]]  # ModuleResult.to_contract()


class FinalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Decision
    reason_code: str
    note: str | None = None


class ReasonCode(BaseModel):
    code: str
    label: str
    note_required: bool


class ReasonCodeList(BaseModel):
    items: list[ReasonCode]


class AuditVerification(BaseModel):
    case_id: str
    ok: bool
    checked: int
    bad_index: int | None = None
    reason: str | None = None


class DecisionResponse(BaseModel):
    case_id: str
    status: CaseStatus
