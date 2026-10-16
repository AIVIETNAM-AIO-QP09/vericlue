"""Bàn duyệt — /v1/review. Ca lưu trong DB; quyết định ghi vào nhật ký băm nối chuỗi (REV-01).

Nhân viên chưa xác thực (PLAT-06): actor cố định `staff-unverified`.

Hồ sơ `GET /cases/{id}` KHÔNG có điểm AI; ý kiến AI ở `/cases/{id}/ai` và chỉ xem được sau khi
nhân viên ghi quyết định ban đầu (nếu chưa → 409).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from vericlue_api.core.errors import ApiError
from vericlue_api.core.state import AppState, get_state
from vericlue_api.schemas.review import (
    AuditVerification,
    CaseStatus,
    DecisionResponse,
    FinalDecisionRequest,
    InitialDecisionRequest,
    Priority,
    ReasonCode,
    ReasonCodeList,
    ReviewAiOpinion,
    ReviewCase,
    ReviewCaseList,
)
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.review_reasons import REASON_CODES, get_reason
from vericlue_api.services.review_store import CaseRecord

router = APIRouter(prefix="/v1/review", tags=["review"])

StateDep = Annotated[AppState, Depends(get_state, scope="function")]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Không có ca này"}}


def _case(state: AppState, case_id: str) -> CaseRecord:
    record = state.reviews.get(case_id)
    if record is None:
        raise ApiError(404, "case_not_found", "Không tìm thấy ca duyệt.")
    return record


@router.get("/reason-codes", response_model=ReasonCodeList)
def list_reason_codes() -> ReasonCodeList:
    """Mã lý do hợp lệ cho quyết định cuối (danh sách tạm — M2 chỉnh)."""
    return ReasonCodeList(
        items=[
            ReasonCode(code=r.code, label=r.label, note_required=r.note_required)
            for r in REASON_CODES
        ]
    )


def _check_reason(code: str, note: str | None) -> None:
    reason = get_reason(code)
    if reason is None:
        raise ApiError(422, "invalid_reason_code", "Mã lý do không có trong danh sách.")
    if reason.note_required and not (note and note.strip()):
        raise ApiError(422, "invalid_reason_code", "Mã lý do này bắt buộc có ghi chú.")


@router.get("/cases", response_model=ReviewCaseList)
def list_cases(
    state: StateDep, status: CaseStatus | None = None, priority: Priority | None = Query(None)
) -> ReviewCaseList:
    return ReviewCaseList(items=[c.summary() for c in state.reviews.list(status, priority)])


@router.get("/cases/{case_id}", response_model=ReviewCase, responses=NOT_FOUND)
def get_case(case_id: str, state: StateDep) -> ReviewCase:
    return _case(state, case_id).to_case()


@router.post(
    "/cases/{case_id}/initial",
    response_model=DecisionResponse,
    responses={
        **NOT_FOUND,
        409: {
            "model": ErrorResponse,
            "description": "initial_already_recorded (đã có quyết định ban đầu) hoặc review_conflict (ghi đồng thời, tải lại rồi thử lại)",
        },
    },
)
def post_initial(case_id: str, body: InitialDecisionRequest, state: StateDep) -> DecisionResponse:
    record = _case(state, case_id)
    if record.initial_decision is not None:
        raise ApiError(409, "initial_already_recorded", "Ca này đã có quyết định ban đầu.")
    state.reviews.record_event(record, "initial", body.decision, note=body.note)
    record.initial_decision = body.decision
    record.status = "initial_decided"
    return DecisionResponse(case_id=record.case_id, status=record.status)


@router.get("/cases/{case_id}/audit/verify", response_model=AuditVerification, responses=NOT_FOUND)
def verify_audit(case_id: str, state: StateDep) -> AuditVerification:
    """Kiểm chuỗi băm của ca (rehash payload đã lưu)."""
    record = _case(state, case_id)
    check = state.reviews.verify(record.case_id)
    return AuditVerification(
        case_id=record.case_id,
        ok=check.ok,
        checked=check.checked,
        bad_index=check.bad_index,
        reason=check.reason,
    )


@router.get(
    "/cases/{case_id}/ai",
    response_model=ReviewAiOpinion,
    responses={
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Chưa có quyết định ban đầu"},
    },
)
def get_ai_opinion(case_id: str, state: StateDep) -> ReviewAiOpinion:
    record = _case(state, case_id)
    if record.initial_decision is None:
        raise ApiError(
            409, "initial_decision_required", "Hãy ghi quyết định ban đầu trước khi xem ý kiến AI."
        )
    return record.ai_opinion(state.settings.provisional_threshold_b)


@router.post(
    "/cases/{case_id}/decision",
    response_model=DecisionResponse,
    responses={
        **NOT_FOUND,
        409: {
            "model": ErrorResponse,
            "description": "initial_decision_required, decision_already_recorded hoặc review_conflict (ghi đồng thời, tải lại rồi thử lại)",
        },
        422: {"model": ErrorResponse, "description": "invalid_reason_code"},
    },
)
def post_decision(case_id: str, body: FinalDecisionRequest, state: StateDep) -> DecisionResponse:
    record = _case(state, case_id)
    if record.initial_decision is None:
        raise ApiError(
            409, "initial_decision_required", "Cần quyết định ban đầu trước quyết định cuối."
        )
    if record.final_decision is not None:
        raise ApiError(409, "decision_already_recorded", "Ca này đã có quyết định cuối.")
    _check_reason(body.reason_code, body.note)
    state.reviews.record_event(
        record, "final", body.decision, reason_code=body.reason_code, note=body.note
    )
    record.final_decision = body.decision
    record.status = "closed"
    return DecisionResponse(case_id=record.case_id, status=record.status)
