"""Model Pydantic khớp `packages/contracts/schemas/session.schema.json` (có test đối chiếu)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RetryHint = Literal[
    "MORE_LIGHT",
    "MOVE_CLOSER",
    "MOVE_BACK",
    "FACE_CENTER",
    "HOLD_STILL",
    "QUIET_PLACE",
    "BRIGHTNESS_UP",
]


class ColorStep(BaseModel):
    rgb: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    hold_ms: int = Field(ge=400, le=650)
    transition_ms: Literal[150] = 150


TurnDirection = Literal["left", "right"]


class DotPoint(BaseModel):
    """Một điểm của đường chấm sáng; x, y theo tỉ lệ màn hình (0–1)."""

    t_ms: int = Field(ge=0)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class Challenge(BaseModel):
    challenge_id: str
    baseline_ms: int = 1000
    color_sequence: list[ColorStep] = Field(min_length=8, max_length=8)
    capture_at_ms: list[int] = Field(default_factory=list)
    expires_at: datetime | None = None
    # LIVE-01: tùy chọn để gói cũ (đã lưu trong phiên) vẫn đọc được.
    turn_order: list[TurnDirection] | None = Field(default=None, min_length=2, max_length=2)
    dot_path: list[DotPoint] | None = Field(default=None, min_length=2)


class CreateSessionResponse(BaseModel):
    session_id: str
    token: str = Field(
        description="Token theo phiên, gửi 'Authorization: Bearer'. TẠM — PLAT-06 thay bằng HMAC + TTL."
    )
    expires_at: datetime = Field(description="Hạn của token (~5 phút)")
    challenge: Challenge


class Signals(BaseModel):
    """Tín hiệu trình duyệt đo; server không tin tuyệt đối. Trường lạ được giữ lại."""

    model_config = ConfigDict(extra="allow")

    color_events: list[dict[str, Any]]
    frame_times: list[dict[str, Any]]


class StepAck(BaseModel):
    step: Literal["media", "signals"]
    received: bool = True


class FinalizeResponse(BaseModel):
    status: Literal["pass", "retry", "review", "voice_challenge"]
    retry_hint: RetryHint | None = None
    voice_prompt: str | None = None
    attempts_left: int | None = None
    challenge: Challenge | None = Field(default=None, description="Chỉ có khi status = retry")


class VoiceResponse(BaseModel):
    status: Literal["pass", "review", "voice_challenge"]
    voice_prompt: str | None = None
    attempts_left: int | None = None


class OtpRequest(BaseModel):
    phone: str = Field(pattern=r"^0[0-9]{9}$")


class OtpSent(BaseModel):
    expires_at: datetime
    attempts_left: int
    simulated_sms: str | None = Field(
        default=None, description="Chỉ có với kênh SMS mô phỏng (bản demo)"
    )


class OtpVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class OtpVerifyResponse(BaseModel):
    status: Literal["pass", "retry"]
    attempts_left: int


class IdCardFields(BaseModel):
    full_name: str | None = None
    id_number: str | None = Field(default=None, pattern=r"^[0-9]{12}$")
    date_of_birth: date | None = None
    sex: Literal["Nam", "Nữ"] | None = None
    address: str | None = None
    issued_on: date | None = None


class IdCardResponse(BaseModel):
    status: Literal["ok", "retry"]
    fields: IdCardFields | None = None
    retry_hint: Literal["QR_UNREADABLE", "QR_INVALID"] | None = None


class IdCardConfirmResponse(BaseModel):
    received: bool = True


class ChallengeResponse(BaseModel):
    expires_at: datetime = Field(description="Hạn mới của token")
    challenge: Challenge


class ErrorResponse(BaseModel):
    error_code: str
    message: str
