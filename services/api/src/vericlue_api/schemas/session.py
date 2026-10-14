"""Model Pydantic khớp `packages/contracts/schemas/session.schema.json` (có test đối chiếu)."""

from __future__ import annotations

from datetime import datetime
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


class Challenge(BaseModel):
    challenge_id: str
    baseline_ms: int = 1000
    color_sequence: list[ColorStep] = Field(min_length=8, max_length=8)
    capture_at_ms: list[int] = Field(default_factory=list)
    expires_at: datetime | None = None


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


class ErrorResponse(BaseModel):
    error_code: str
    message: str
