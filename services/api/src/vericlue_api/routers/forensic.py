"""Giám định — /v1/forensic. Phân tích thật theo đoạn (FOR-01) khi USE_MOCK_MODELS khác true;
chữ ký báo cáo vẫn MOCK (FOR-04/PLAT-06 cấp khóa Ed25519)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, Request, UploadFile
from fastapi.responses import HTMLResponse

from vericlue_api.core.errors import ApiError
from vericlue_api.core.state import AppState, get_state
from vericlue_api.routers.sessions import resolve_scenario
from vericlue_api.schemas.forensic import ForensicJob, JobCreated, VerifyRequest, VerifyResponse
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.forensic_runner import release_slot, reserve_slot, run_forensic_job
from vericlue_api.services.uploads import read_limited

router = APIRouter(prefix="/v1/forensic", tags=["forensic"])

StateDep = Annotated[AppState, Depends(get_state, scope="function")]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Không có job này"}}


@router.post(
    "/jobs",
    response_model=JobCreated,
    responses={
        429: {"model": ErrorResponse, "description": "forensic_busy: hàng đợi giám định đang đầy"}
    },
)
async def create_job(
    request: Request,
    background_tasks: BackgroundTasks,
    state: StateDep,
    file: Annotated[UploadFile, File(description="Video hoặc âm thanh cần giám định")],
    x_mock_scenario: Annotated[
        str | None, Header(description="Chỉ khi USE_MOCK_MODELS=true: chọn kịch bản mock")
    ] = None,
) -> JobCreated:
    data = await read_limited(file, state.settings.max_upload_mb)  # hash tính trên byte gốc
    reserved = not state.forensic.mock
    if reserved and not reserve_slot():
        raise ApiError(429, "forensic_busy", "Đang xử lý nhiều job giám định; hãy thử lại sau.")
    try:
        job = state.forensic.create(data, file.filename, resolve_scenario(x_mock_scenario, state))
    except BaseException:
        if reserved:
            release_slot()
        raise
    if job.status == "queued":
        # Transaction của request đã commit (scope="function") trước khi tác vụ nền bắt đầu.
        background_tasks.add_task(run_forensic_job, request.app.state.vericlue, job.job_id)
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
        409: {
            "model": ErrorResponse,
            "description": "job_not_ready: job chưa xong hoặc đã thất bại nên chưa có báo cáo",
        },
        200: {"description": "Báo cáo HTML; chữ ký trong header X-VeriClue-Signature"},
    },
)
def get_report(job_id: str, state: StateDep) -> HTMLResponse:
    job = state.forensic.get(job_id)
    if job is not None and job.status != "done":
        # Không ký báo cáo cho job đang chạy hoặc thất bại (kết luận còn trống).
        raise ApiError(409, "job_not_ready", "Job chưa hoàn tất hoặc đã thất bại; chưa có báo cáo.")
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
