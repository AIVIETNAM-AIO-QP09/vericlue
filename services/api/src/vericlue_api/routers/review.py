"""Bàn duyệt — /v1/review. Dữ liệu mock (TẠM — REV-01 nối DB và nhật ký băm).

Hồ sơ `GET /cases/{id}` KHÔNG có điểm AI; ý kiến AI ở `/cases/{id}/ai` và chỉ xem được sau khi
nhân viên ghi quyết định ban đầu (nếu chưa → 409).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from vericlue_api.core.errors import ApiError
from vericlue_api.core.state import AppState, get_state
from vericlue_api.schemas.review import (
    CaseStatus,
    DecisionResponse,
    FinalDecisionRequest,
    InitialDecisionRequest,
    Priority,
    ReviewAiOpinion,
    ReviewCase,
    ReviewCaseList,
)
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.review_store import CaseRecord

router = APIRouter(prefix="/v1/review", tags=["review"])

StateDep = Annotated[AppState, Depends(get_state, scope="function")]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Không có ca này"}}


def _case(state: AppState, case_id: str) -> CaseRecord:
    record = state.reviews.get(case_id)
    if record is None:
        raise ApiError(404, "case_not_found", "Không tìm thấy ca duyệt.")
    return record


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
        409: {"model": ErrorResponse, "description": "Đã có quyết định ban đầu"},
    },
)
def post_initial(case_id: str, body: InitialDecisionRequest, state: StateDep) -> DecisionResponse:
    record = _case(state, case_id)
    if record.initial_decision is not None:
        raise ApiError(409, "initial_already_recorded", "Ca này đã có quyết định ban đầu.")
    record.initial_decision = body.decision
    record.status = "initial_decided"
    state.reviews.record_event(record, "initial", body.decision, note=body.note)
    return DecisionResponse(case_id=record.case_id, status=record.status)


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
        409: {"model": ErrorResponse, "description": "Chưa có quyết định ban đầu"},
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
    record.final_decision = body.decision
    record.status = "closed"
    state.reviews.record_event(
        record, "final", body.decision, reason_code=body.reason_code, note=body.note
    )
    return DecisionResponse(case_id=record.case_id, status=record.status)
