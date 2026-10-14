"""Giám định — /v1/forensic. Dữ liệu mock (TẠM — FOR-01/FOR-04 làm thật, PLAT-06 cấp khóa Ed25519)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import HTMLResponse

from vericlue_api.core.errors import ApiError
from vericlue_api.core.state import AppState, get_state
from vericlue_api.routers.sessions import resolve_scenario
from vericlue_api.schemas.forensic import ForensicJob, JobCreated, VerifyRequest, VerifyResponse
from vericlue_api.schemas.session import ErrorResponse

router = APIRouter(prefix="/v1/forensic", tags=["forensic"])

StateDep = Annotated[AppState, Depends(get_state)]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Không có job này"}}


@router.post("/jobs", response_model=JobCreated)
async def create_job(
    state: StateDep,
    file: Annotated[UploadFile, File(description="Video hoặc âm thanh cần giám định")],
    x_mock_scenario: Annotated[
        str | None, Header(description="Chỉ khi USE_MOCK_MODELS=true: chọn kịch bản mock")
    ] = None,
) -> JobCreated:
    data = await file.read()  # hash tính trên byte gốc
    job = state.forensic.create(data, file.filename, resolve_scenario(x_mock_scenario, state))
    return JobCreated(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=ForensicJob, responses=NOT_FOUND)
def get_job(job_id: str, state: StateDep) -> ForensicJob:
    job = state.forensic.get(job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "Không tìm thấy job giám định.")
    return job


@router.get(
    "/jobs/{job_id}/report",
    response_class=HTMLResponse,
    responses={
        **NOT_FOUND,
        200: {"description": "Báo cáo HTML; chữ ký trong header X-VeriClue-Signature"},
    },
)
def get_report(job_id: str, state: StateDep) -> HTMLResponse:
    report = state.forensic.report(job_id)
    if report is None:
        raise ApiError(404, "job_not_found", "Không tìm thấy job giám định.")
    html, digest, signature = report
    return HTMLResponse(
        html, headers={"X-VeriClue-Report-SHA256": digest, "X-VeriClue-Signature": signature}
    )


@router.post("/verify", response_model=VerifyResponse)
def verify_report(body: VerifyRequest, state: StateDep) -> VerifyResponse:
    return VerifyResponse(valid=state.forensic.verify(body.report_sha256, body.signature))
