"""Bàn duyệt — /v1/review. Ca lưu trong DB; quyết định ghi vào nhật ký băm nối chuỗi (REV-01).

PLAT-06: credential nhân viên bắt buộc, actor lấy từ cấu hình server.

Hồ sơ `GET /cases/{id}` KHÔNG có điểm AI; ý kiến AI ở `/cases/{id}/ai` và chỉ xem được sau khi
nhân viên ghi quyết định ban đầu (nếu chưa → 409).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from vericlue_api.core.errors import ApiError
from vericlue_api.core.staff_access import staff_bearer
from vericlue_api.core.state import AppState, get_state
from vericlue_api.db.models import SessionRow
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
    ReviewIdentity,
)
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.review_reasons import REASON_CODES, get_reason
from vericlue_api.services.review_store import CaseRecord

router = APIRouter(
    prefix="/v1/review",
    tags=["review"],
    dependencies=[Depends(staff_bearer)],
    responses={
        401: {
            "model": ErrorResponse,
            "description": "Thiếu hoặc sai credential nhân viên",
        },
        410: {"model": ErrorResponse, "description": "Dữ liệu hết thời hạn lưu trữ"},
        503: {
            "model": ErrorResponse,
            "description": "Credential nhân viên, kho dữ liệu hoặc chức năng riêng tư chưa sẵn sàng",
        },
    },
)

StateDep = Annotated[AppState, Depends(get_state, scope="function")]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Không có ca này"}}


def _case(state: AppState, case_id: str, *, metadata_only: bool = False) -> CaseRecord:
    record = state.reviews.get_metadata(case_id) if metadata_only else state.reviews.get(case_id)
    if record is None:
        raise ApiError(404, "case_not_found", "Không tìm thấy ca duyệt.")
    if state.privacy.enabled:
        state.privacy.lock_session(record.session_id)
        state.privacy.audit(record.session_id, actor=state.reviews.actor, action="case_access")
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
    records = state.reviews.list(status, priority)
    if state.privacy.enabled:
        for record in sorted(records, key=lambda r: r.session_id):
            state.privacy.lock_session(record.session_id)
            state.privacy.audit(record.session_id, actor=state.reviews.actor, action="case_listed")
    return ReviewCaseList(items=[c.summary() for c in records])


@router.get("/cases/{case_id}", response_model=ReviewCase, responses=NOT_FOUND)
def get_case(case_id: str, state: StateDep) -> ReviewCase:
    return _case(state, case_id).to_case()


def _identity(case_id: str, state: AppState, *, reveal: bool) -> ReviewIdentity:
    if not state.privacy.enabled or state.reviews.actor == "staff-unverified":
        raise ApiError(503, "privacy_unavailable", "Chức năng xem thông tin chưa sẵn sàng.")
    record = _case(state, case_id)
    row = state.db.get(SessionRow, record.session_id)
    snapshot = state.privacy.open_json(record.session_id, "session", row.payload)
    fields = snapshot.get("id_confirmed_fields") or snapshot.get("id_fields") or {}
    number = snapshot.get("sensitive_confirmed_id_number") or snapshot.get("sensitive_id_number")
    dob = fields.get("date_of_birth")
    state.privacy.audit(
        record.session_id,
        actor=state.reviews.actor,
        action="identity_revealed" if reveal else "identity_masked",
    )
    return ReviewIdentity(
        case_id=case_id,
        masked=not reveal,
        full_name=fields.get("full_name"),
        id_number=number if reveal or not number else "*" * 9 + number[-3:],
        date_of_birth=dob if reveal or not dob else dob[:4],
        sex=fields.get("sex"),
        address=fields.get("address"),
        edited_fields=snapshot.get("id_edited", []),
    )


@router.get("/cases/{case_id}/identity", response_model=ReviewIdentity, responses=NOT_FOUND)
def get_identity(case_id: str, state: StateDep) -> ReviewIdentity:
    return _identity(case_id, state, reveal=False)


@router.post("/cases/{case_id}/identity/reveal", response_model=ReviewIdentity, responses=NOT_FOUND)
def reveal_identity(case_id: str, state: StateDep) -> ReviewIdentity:
    """Explicit staff action; an access event is committed before any full fields are sent."""
    return _identity(case_id, state, reveal=True)


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
    record = _case(state, case_id, metadata_only=True)
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
    return record.ai_opinion(state.settings.router_config.face.b)


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
