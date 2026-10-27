"""Phiên eKYC — /v1/sessions. Phản hồi cho người dân KHÔNG BAO GIỜ chứa điểm số hay chữ 'giả mạo'."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from vericlue_api.core.errors import ApiError
from vericlue_api.core.security import bearer_scheme, require_session
from vericlue_api.core.state import AppState, get_state
from vericlue_api.schemas.result import SignedResult, SigningKey
from vericlue_api.schemas.session import (
    AccountReceipt,
    ChallengeResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    DeviceProofRequest,
    DeviceProofResponse,
    ErrorResponse,
    FinalizeRequest,
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
from vericlue_api.services.uploads import read_limited
from vericlue_ml.mock import SCENARIOS

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])
keys_router = APIRouter(prefix="/v1", tags=["integration"])

# 401: thiếu/sai/hết hạn token. 409: sai trạng thái, bước đã nhận hoặc thử thách hết hạn.
SESSION_ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse, "description": "Thiếu hoặc sai token phiên"},
    409: {
        "model": ErrorResponse,
        "description": "Sai trạng thái, phiên đã kết thúc, thiếu bước hoặc sai/hết hạn mã thử thách; bước gửi trùng cũng trả 409.",
    },
    503: {"model": ErrorResponse, "description": "Kho dữ liệu hoặc luồng xác minh chưa sẵn sàng"},
}

SessionDep = Annotated[Session, Depends(require_session)]
StateDep = Annotated[AppState, Depends(get_state, scope="function")]


@keys_router.get(
    "/result-signing-key", response_model=SigningKey, responses={503: {"model": ErrorResponse}}
)
def result_key(request: Request, response: Response) -> SigningKey:
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.vericlue.settings.result_signer.public_key()


@router.get("/{session_id}/result", response_model=SignedResult, responses=SESSION_ERRORS)
def signed_result(session: SessionDep, state: StateDep, response: Response) -> SignedResult:
    response.headers["Cache-Control"] = "no-store"
    return state.signed_results.issue(session)


def resolve_scenario(header: str | None, state: AppState) -> str:
    """Kịch bản mock chọn qua header `X-Mock-Scenario`; chỉ có tác dụng khi USE_MOCK_MODELS=true."""
    if header is None or not state.settings.use_mock_models:
        return "genuine"
    if header not in SCENARIOS:
        raise ApiError(422, "unknown_scenario", f"Kịch bản mock không có: {header}")
    return header


@router.post(
    "",
    response_model=CreateSessionResponse,
    response_model_exclude_none=True,
    responses={
        503: {"model": ErrorResponse, "description": "Luồng purpose chưa hỗ trợ mô hình thật"}
    },
)
def create_session(
    state: StateDep,
    request: CreateSessionRequest | None = None,
    x_mock_scenario: Annotated[
        str | None,
        Header(
            description="Chỉ khi USE_MOCK_MODELS=true: chọn kịch bản mock (genuine, print, ...)"
        ),
    ] = None,
) -> CreateSessionResponse:
    return state.flow.create(resolve_scenario(x_mock_scenario, state), request)


@router.get(
    "/{session_id}/account",
    response_model=AccountReceipt,
    responses=SESSION_ERRORS,
)
def account_receipt(session: SessionDep, state: StateDep, response: Response) -> AccountReceipt:
    response.headers["Cache-Control"] = "no-store"
    return AccountReceipt.model_validate(state.accounts.receipt_for_session(session))


@router.post(
    "/{session_id}/device-proof",
    response_model=DeviceProofResponse,
    responses=SESSION_ERRORS,
)
def device_proof(
    session: SessionDep,
    state: StateDep,
    body: DeviceProofRequest,
    response: Response,
) -> DeviceProofResponse:
    response.headers["Cache-Control"] = "no-store"
    state.flow.account_auth.verify(session, body.signature)
    return DeviceProofResponse()


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
    media_signature: Annotated[
        str | None,
        Form(
            max_length=160,
            description="SEC-02: chữ ký DER ECDSA P-256/SHA-256 base64 của manifest media",
        ),
    ] = None,
    video: Annotated[UploadFile | None, File(description="Đoạn video lúc phát màu")] = None,
    challenge_id: Annotated[
        str | None, Form(description="Mã thử thách; bắt buộc khi có purpose")
    ] = None,
) -> StepAck:
    state.flow.ensure_binding(session, challenge_id)
    state.flow.ensure_face_step_allowed(session, "media")
    image_bytes = await read_limited(image, state.settings.max_upload_mb)
    video_bytes = await read_limited(video, state.settings.max_upload_mb) if video else None
    state.flow.accept_media(
        session,
        image=image_bytes,
        image_filename=image.filename,
        video=video_bytes,
        video_filename=video.filename if video else None,
        media_signature=media_signature,
    )
    return StepAck(step="media")


@router.post("/{session_id}/signals", response_model=StepAck, responses=SESSION_ERRORS)
def upload_signals(session: SessionDep, state: StateDep, signals: Signals) -> StepAck:
    state.flow.ensure_binding(session, signals.challenge_id)
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
def finalize(
    session: SessionDep, state: StateDep, request: FinalizeRequest | None = None
) -> FinalizeResponse:
    return state.flow.finalize(session, request.challenge_id if request else None)


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
    media_signature: Annotated[
        str | None,
        Form(
            max_length=160, description="SEC-02: chữ ký manifest gồm audio/video và audio_offset_ms"
        ),
    ] = None,
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
    voice_challenge_id: Annotated[
        str | None, Form(description="Mã lần đọc; bắt buộc khi có purpose")
    ] = None,
) -> VoiceResponse:
    state.flow.ensure_binding(session, voice_challenge_id, voice=True)
    state.flow.ensure_voice_allowed(session)  # kiểm TRƯỚC khi ghi bất kỳ file nào
    audio_bytes = await read_limited(audio, state.settings.max_upload_mb)
    video_bytes = await read_limited(video, state.settings.max_upload_mb) if video else None
    voice_video = state.flow.accept_voice_media(
        session,
        audio=audio_bytes,
        audio_filename=audio.filename,
        video=video_bytes,
        video_filename=video.filename if video else None,
        media_signature=media_signature,
        audio_offset_ms=audio_offset_ms,
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
    if session.account_id:
        if session.purpose != "recovery":
            raise ApiError(409, "step_not_allowed", "Bước này chưa phù hợp.")
        state.flow.account_auth.check_phone(session, body.phone)
    return state.identity.send_otp(session, body.phone)


@router.post(
    "/{session_id}/otp/verify",
    response_model=OtpVerifyResponse,
    responses=STAGE_A_ERRORS,
    dependencies=[Depends(bearer_scheme)],
)
def verify_otp(session: SessionDep, state: StateDep, body: OtpVerifyRequest) -> OtpVerifyResponse:
    state.flow.ensure_open(session)
    if session.account_id:
        if session.purpose != "recovery":
            raise ApiError(409, "step_not_allowed", "Bước này chưa phù hợp.")
        state.flow.account_auth.current(session)
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
    state.identity.ensure_card_upload_allowed(session)
    limit = state.settings.max_upload_mb
    front_bytes = await read_limited(front, limit)
    back_bytes = await read_limited(back, limit)
    return await run_in_threadpool(
        state.identity.accept_images,
        session,
        front_bytes,
        back_bytes,
        qr,
        front_filename=front.filename,
        back_filename=back.filename,
    )


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
