"""Giám định — /v1/forensic. Phân tích thật theo đoạn (FOR-01) khi USE_MOCK_MODELS khác true;
PLAT-06 ký báo cáo HTML thật bằng Ed25519, PDF/JSON ENFSI thuộc FOR-04."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from vericlue_api.core.errors import ApiError
from vericlue_api.core.staff_access import staff_bearer
from vericlue_api.core.state import AppState, get_state
from vericlue_api.routers.sessions import resolve_scenario
from vericlue_api.schemas.forensic import (
    ForensicJob,
    JobCreated,
    ReviewAuditVerifyRequest,
    ReviewAuditVerifyResponse,
    VerifyRequest,
    VerifyResponse,
)
from vericlue_api.schemas.result import SigningKey
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.forensic_runner import release_slot, reserve_slot, run_forensic_job
from vericlue_api.services.forensic_service import MOCK_SIGNATURE_PREFIX
from vericlue_api.services.pdf_renderer import PdfRenderer
from vericlue_api.services.pdf_report_bundle import export_pdf_bundle
from vericlue_api.services.review_audit_link import check_review_anchor
from vericlue_api.services.uploads import read_limited

router = APIRouter(
    prefix="/v1/forensic",
    tags=["forensic"],
    dependencies=[Depends(staff_bearer)],
    responses={
        401: {"model": ErrorResponse, "description": "Thiếu hoặc sai credential nhân viên"},
        503: {
            "model": ErrorResponse,
            "description": "Credential nhân viên, khóa report hoặc kho dữ liệu chưa sẵn sàng",
        },
    },
)

StateDep = Annotated[AppState, Depends(get_state, scope="function")]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Không có job này"}}


@router.get("/signing-key", response_model=SigningKey)
def signing_key(request: Request) -> SigningKey:
    """Staff-only public key; does not connect to DB or start any model."""
    return request.app.state.vericlue.settings.report_signer.public_key()


@router.post(
    "/jobs",
    response_model=JobCreated,
    responses={
        429: {"model": ErrorResponse, "description": "forensic_busy: hàng đợi giám định đang đầy"},
        404: {"model": ErrorResponse, "description": "Không tìm thấy ca cần liên kết"},
        409: {
            "model": ErrorResponse,
            "description": "Ca chưa có quyết định ban đầu, file không khớp hoặc nhật ký không hợp lệ",
        },
        410: {"model": ErrorResponse, "description": "Media của hồ sơ đã hết thời hạn lưu trữ"},
    },
)
async def create_job(
    request: Request,
    background_tasks: BackgroundTasks,
    state: StateDep,
    file: Annotated[UploadFile, File(description="Video hoặc âm thanh cần giám định")],
    review_case_id: Annotated[
        str | None,
        Form(
            pattern=r"^case_[A-Za-z0-9_-]{1,64}$",
            description="Tùy chọn: ca đã có quyết định ban đầu; server đối chiếu byte media",
        ),
    ] = None,
    x_mock_scenario: Annotated[
        str | None, Header(description="Chỉ khi USE_MOCK_MODELS=true: chọn kịch bản mock")
    ] = None,
) -> JobCreated:
    data = await read_limited(file, state.settings.max_upload_mb)  # hash tính trên byte gốc
    reserved = not state.forensic.mock
    if reserved and not reserve_slot():
        raise ApiError(429, "forensic_busy", "Đang xử lý nhiều job giám định; hãy thử lại sau.")
    try:
        job = await run_in_threadpool(
            state.forensic.create,
            data,
            file.filename,
            resolve_scenario(x_mock_scenario, state),
            review_case_id=review_case_id,
        )
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
        200: {
            "description": "HTML; job real ký Ed25519, mock không có chữ ký hợp lệ; metadata trong X-VeriClue-Signature/Signature-Algorithm/Key-Id/Report-SHA256"
        },
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
    headers = {"X-VeriClue-Report-SHA256": digest, "X-VeriClue-Signature": signature}
    if signature.startswith(MOCK_SIGNATURE_PREFIX):
        headers["X-VeriClue-Signature-Algorithm"] = "MOCK"
    else:
        headers["X-VeriClue-Signature-Algorithm"] = "Ed25519"
        headers["X-VeriClue-Key-Id"] = state.forensic.report_signer().key_id
    return HTMLResponse(html, headers=headers)


@router.post("/verify", response_model=VerifyResponse)
def verify_report(body: VerifyRequest, request: Request) -> VerifyResponse:
    signer = request.app.state.vericlue.settings.report_signer
    return VerifyResponse(valid=signer.verify(body.report_sha256, body.signature))


@router.post(
    "/review-audit/verify",
    response_model=ReviewAuditVerifyResponse,
    response_model_exclude_none=True,
)
def verify_signed_review_audit(
    body: ReviewAuditVerifyRequest, request: Request
) -> ReviewAuditVerifyResponse:
    """Verify signed JSON first, then compare its checkpoint with DB; does not verify PDF bytes."""
    root = request.app.state.vericlue
    signer = root.settings.report_signer
    try:
        manifest = signer.verify_manifest(body.report_json.encode("ascii"), body.signature)
    except (ValueError, UnicodeError):
        return ReviewAuditVerifyResponse(
            signature_valid=False, ok=False, status="invalid_signature"
        )
    if manifest.job.review_audit is None:
        return ReviewAuditVerifyResponse(signature_valid=True, ok=False, status="unlinked")
    # No model startup and no DB access until the signature/format and linked anchor are valid.
    with root.database.sessions.begin() as db:
        return check_review_anchor(db, manifest.job.review_audit)


@router.get(
    "/jobs/{job_id}/report-bundle",
    response_class=Response,
    responses={
        **NOT_FOUND,
        200: {
            "description": "ZIP gồm report.pdf, report.json chuẩn hóa và report.sig Ed25519 tách rời; không phải PAdES/ENFSI",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
        409: {"model": ErrorResponse, "description": "Job chưa xong hoặc chỉ là bản mô phỏng"},
    },
)
def download_report_bundle(job_id: str, state: StateDep) -> Response:
    bundle = export_pdf_bundle(state.forensic, PdfRenderer(state.settings), job_id)
    return Response(
        bundle,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{job_id}-report.zip"',
            "Cache-Control": "no-store",
        },
    )
