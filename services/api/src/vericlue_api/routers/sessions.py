"""Phiên eKYC — /v1/sessions. Phản hồi cho người dân KHÔNG BAO GIỜ chứa điểm số hay chữ 'giả mạo'."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from starlette.concurrency import run_in_threadpool

from vericlue_api.core.errors import ApiError
from vericlue_api.core.security import bearer_scheme, require_session
from vericlue_api.core.state import AppState, get_state
from vericlue_api.schemas.session import (
    ChallengeResponse,
    CreateSessionResponse,
    ErrorResponse,
    FinalizeResponse,
    IdCardConfirmResponse,
    IdCardFields,
    IdCardResponse,
    OtpRequest,
    OtpSent,
    OtpVerifyRequest,
    OtpVerifyResponse,
    Signals,
    StepAck,
    VoiceResponse,
)
from vericlue_api.services.session_store import Session
from vericlue_api.services.uploads import read_limited, save_upload
from vericlue_ml.mock import SCENARIOS

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])

# 401: thiếu/sai token. 409: sai trạng thái (voice_not_requested, session_closed — đã cài ở PLAT-04) và
# bước đã nhận trong lượt này (hợp đồng đã khai báo, PLAT-06 cài đặt).
SESSION_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai token phiên"},
    409: {
        "model": ErrorResponse,
        "description": "Sai trạng thái: voice_not_requested (finalize chưa yêu cầu đọc câu), session_closed (phiên đã vào bàn duyệt). Bước đã nhận trong lượt này cũng 409 (PLAT-06).",
    },
}

SessionDep = Annotated[Session, Depends(require_session)]
StateDep = Annotated[AppState, Depends(get_state, scope="function")]


def resolve_scenario(header: str | None, state: AppState) -> str:
    """Kịch bản mock chọn qua header `X-Mock-Scenario`; chỉ có tác dụng khi USE_MOCK_MODELS=true."""
    if header is None or not state.settings.use_mock_models:
        return "genuine"
    if header not in SCENARIOS:
        raise ApiError(422, "unknown_scenario", f"Kịch bản mock không có: {header}")
    return header


@router.post("", response_model=CreateSessionResponse, response_model_exclude_none=True)
def create_session(
    state: StateDep,
    x_mock_scenario: Annotated[
        str | None,
        Header(
            description="Chỉ khi USE_MOCK_MODELS=true: chọn kịch bản mock (genuine, print, ...)"
        ),
    ] = None,
) -> CreateSessionResponse:
    return state.flow.create(resolve_scenario(x_mock_scenario, state))


@router.post(
    "/{session_id}/media",
    response_model=StepAck,
    responses=SESSION_ERRORS,
    dependencies=[Depends(bearer_scheme)],
)
async def upload_media(
    session: SessionDep,
    state: StateDep,
    image: Annotated[UploadFile, File(description="Ảnh mặt chất lượng cao")],
    video: Annotated[UploadFile | None, File(description="Đoạn video lúc phát màu")] = None,
) -> StepAck:
    media_dir = state.settings.media_dir
    session.images = [
        save_upload(
            media_dir,
            session.session_id,
            "face_image",
            image.filename,
            await read_limited(image, state.settings.max_upload_mb),
        )
    ]
    if video is not None:
        session.video = save_upload(
            media_dir,
            session.session_id,
            "face_video",
            video.filename,
            await read_limited(video, state.settings.max_upload_mb),
        )
    return StepAck(step="media")


@router.post("/{session_id}/signals", response_model=StepAck, responses=SESSION_ERRORS)
def upload_signals(session: SessionDep, state: StateDep, signals: Signals) -> StepAck:
    state.flow.accept_signals(session, signals)
    return StepAck(step="signals")


@router.post(
    "/{session_id}/finalize",
    response_model=FinalizeResponse,
    response_model_exclude_none=True,
    responses={
        **SESSION_ERRORS,
        503: {"model": ErrorResponse, "description": "Kho dữ liệu đang bận hoặc không khả dụng"},
    },
)
def finalize(session: SessionDep, state: StateDep) -> FinalizeResponse:
    return state.flow.finalize(session)


@router.post(
    "/{session_id}/voice",
    response_model=VoiceResponse,
    response_model_exclude_none=True,
    responses={
        **SESSION_ERRORS,
        503: {"model": ErrorResponse, "description": "Kho dữ liệu đang bận hoặc không khả dụng"},
    },
)
async def voice(
    session: SessionDep,
    state: StateDep,
    audio: Annotated[UploadFile, File(description="Âm thanh lúc đọc câu")],
    video: Annotated[UploadFile | None, File(description="Video lúc đọc câu")] = None,
    audio_offset_ms: Annotated[
        int | None,
        Form(
            ge=-5000,
            le=5000,
            description=(
                "Thời điểm WAV bắt đầu, tính bằng ms từ khung hình đầu của video "
                "(dương = WAV bắt đầu sau). Dùng để căn khớp môi; chỉ có khi gửi video."
            ),
        ),
    ] = None,
) -> VoiceResponse:
    state.flow.ensure_voice_allowed(session)  # kiểm TRƯỚC khi ghi bất kỳ file nào
    media_dir = state.settings.media_dir
    session.audio = save_upload(
        media_dir,
        session.session_id,
        "voice_audio",
        audio.filename,
        await read_limited(audio, state.settings.max_upload_mb),
    )
    voice_video: Path | None = None
    if video is not None:
        voice_video = save_upload(
            media_dir,
            session.session_id,
            "voice_video",
            video.filename,
            await read_limited(video, state.settings.max_upload_mb),
        )
    return await run_in_threadpool(
        state.flow.voice, session, voice_video=voice_video, audio_offset_ms=audio_offset_ms
    )


# --- Giai đoạn A: OTP mô phỏng (FLOW-02), CCCD (FLOW-03) ------------------------------------
STAGE_A_ERRORS: dict[int | str, dict] = {
    401: SESSION_ERRORS[401],
    409: {
        "model": ErrorResponse,
        "description": "session_closed; OTP: otp_not_requested, otp_expired, otp_locked, otp_already_verified, otp_too_many; CCCD: id_card_not_received",
    },
}


@router.post(
    "/{session_id}/otp",
    response_model=OtpSent,
    response_model_exclude_none=True,
    responses=STAGE_A_ERRORS,
    dependencies=[Depends(bearer_scheme)],
)
def send_otp(session: SessionDep, state: StateDep, body: OtpRequest) -> OtpSent:
    """Gửi mã 6 số (hạn 2 phút, sai 5 lần thì khóa). Gọi lại = mã mới, mã cũ hết hiệu lực."""
    state.flow.ensure_open(session)
    return state.identity.send_otp(session, body.phone)


@router.post(
    "/{session_id}/otp/verify",
    response_model=OtpVerifyResponse,
    responses=STAGE_A_ERRORS,
    dependencies=[Depends(bearer_scheme)],
)
def verify_otp(session: SessionDep, state: StateDep, body: OtpVerifyRequest) -> OtpVerifyResponse:
    state.flow.ensure_open(session)
    return state.identity.verify_otp(session, body.code)


@router.post(
    "/{session_id}/id-card",
    response_model=IdCardResponse,
    response_model_exclude_none=True,
    responses=STAGE_A_ERRORS,
    dependencies=[Depends(bearer_scheme)],
)
async def upload_id_card(
    session: SessionDep,
    state: StateDep,
    front: Annotated[UploadFile, File(description="Ảnh mặt trước CCCD")],
    back: Annotated[UploadFile, File(description="Ảnh mặt sau CCCD (có QR)")],
    qr: Annotated[
        str | None, Form(description="Chuỗi QR app đã đọc ở mặt sau; thiếu thì trả retry")
    ] = None,
) -> IdCardResponse:
    state.flow.ensure_open(session)
    limit = state.settings.max_upload_mb
    media_dir = state.settings.media_dir
    session.id_front = save_upload(
        media_dir, session.session_id, "id_front", front.filename, await read_limited(front, limit)
    )
    session.id_back = save_upload(
        media_dir, session.session_id, "id_back", back.filename, await read_limited(back, limit)
    )
    return state.identity.accept_id_card(session, qr)


@router.post(
    "/{session_id}/id-card/confirm",
    response_model=IdCardConfirmResponse,
    responses=STAGE_A_ERRORS,
    dependencies=[Depends(bearer_scheme)],
)
def confirm_id_card(
    session: SessionDep, state: StateDep, body: IdCardFields
) -> IdCardConfirmResponse:
    """Thông tin người dùng xác nhận; sửa khác QR thì ghi chú cho nhân viên duyệt."""
    state.flow.ensure_open(session)
    return state.identity.confirm_id_card(session, body)


@router.post(
    "/{session_id}/challenge",
    response_model=ChallengeResponse,
    response_model_exclude_none=True,
    responses={
        401: SESSION_ERRORS[401],
        409: {"model": ErrorResponse, "description": "session_closed, session_too_long"},
    },
    dependencies=[Depends(bearer_scheme)],
)
def refresh_challenge(session: SessionDep, state: StateDep) -> ChallengeResponse:
    """Thử thách mới cho phần khuôn mặt và gia hạn token (ADR-0017 §2, giới hạn tổng 15 phút)."""
    return state.flow.refresh_challenge(session)
