"""Model Pydantic khớp `packages/contracts/schemas/session.schema.json` (có test đối chiếu)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RetryHint = Literal[
    "MORE_LIGHT",
    "MOVE_CLOSER",
    "MOVE_BACK",
    "FACE_CENTER",
    "HOLD_STILL",
    "QUIET_PLACE",
    "BRIGHTNESS_UP",
]
SessionPurpose = Literal["onboarding", "reauth", "recovery"]


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: SessionPurpose
    device_public_key_spki: str | None = Field(default=None, max_length=256)
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{16,128}$")
    reference_image_id: str | None = Field(default=None, pattern=r"^ref_[A-Za-z0-9_-]{1,120}$")
    account_id: str | None = Field(default=None, pattern=r"^acct_[0-9a-f]{32}$")
    device_id: str | None = Field(default=None, pattern=r"^dev_[0-9a-f]{32}$")


class AccountReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    account_id: str = Field(pattern=r"^acct_[0-9a-f]{32}$")
    device_id: str = Field(pattern=r"^dev_[0-9a-f]{32}$")
    expires_at: datetime


class DeviceChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(max_length=2048)
    expires_at: datetime


class DeviceProofRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signature: str = Field(min_length=8, max_length=160)


class DeviceProofResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    received: Literal[True] = True


class GazePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0.1, le=0.9)
    y: float = Field(ge=0.1, le=0.9)
    at_ms: int = Field(ge=0)


class DynamicChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1, 2]
    session_id: str
    nonce: str
    gaze_points: list[GazePoint] = Field(min_length=8, max_length=8)
    head_turns: list[Literal["left", "right", "center"]] = Field(min_length=3, max_length=3)
    head_start_at_ms: int = Field(ge=0)
    head_duration_ms: Literal[6000, 12000]
    voice_start_at_ms: int = Field(ge=0)
    voice_prompt: str
    voice_challenge_id: str
    frontal_capture_at_ms: int = Field(ge=0)

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Protocol version must be an integer")
        return value

    @model_validator(mode="after")
    def head_timing(self):
        if self.head_duration_ms != {1: 6000, 2: 12000}[self.version]:
            raise ValueError("Head duration differs from protocol")
        end = self.head_start_at_ms + self.head_duration_ms
        if end > 30000 or self.voice_start_at_ms != end:
            raise ValueError("Invalid head/voice timeline")
        return self


class FinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str


class ColorStep(BaseModel):
    rgb: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    hold_ms: int = Field(ge=400, le=650)
    transition_ms: Literal[150] = 150


class Challenge(BaseModel):
    media_nonce: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    challenge_id: str
    baseline_ms: int = 1000
    color_sequence: list[ColorStep] = Field(min_length=8, max_length=8)
    capture_at_ms: list[int] = Field(default_factory=list)
    expires_at: datetime | None = None
    dynamic: DynamicChallenge | None = None


class CreateSessionResponse(BaseModel):
    evaluation_mode: Literal["standard", "manual_demo"] = Field(
        default="standard", exclude_if=lambda v: v == "standard"
    )
    demo_policy_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    session_id: str
    token: str = Field(
        description="Token HMAC-SHA256 theo phiên, có hạn; gửi Authorization: Bearer. DB chỉ lưu hash token."
    )
    expires_at: datetime = Field(description="Hạn của token (~5 phút)")
    challenge: Challenge
    purpose: SessionPurpose | None = None
    nonce: str | None = None
    device_challenge: DeviceChallenge | None = None

    @model_validator(mode="after")
    def evaluation_binding(self):
        if (self.evaluation_mode == "manual_demo") != (self.demo_policy_id is not None):
            raise ValueError("Evaluation mode requires matching policy binding")
        return self


class Signals(BaseModel):
    """Tín hiệu trình duyệt đo; server không tin tuyệt đối. Trường lạ được giữ lại."""

    model_config = ConfigDict(extra="allow")

    color_events: list[dict[str, Any]]
    frame_times: list[dict[str, Any]]
    challenge_id: str | None = None


class StepAck(BaseModel):
    step: Literal["media", "signals"]
    received: bool = True


class FinalizeResponse(BaseModel):
    evaluation_mode: Literal["standard", "manual_demo"] = Field(
        default="standard", exclude_if=lambda v: v == "standard"
    )
    demo_policy_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    demo_complete: bool = Field(default=False, exclude_if=lambda v: v is False)
    status: Literal["pass", "retry", "review", "voice_challenge", "deny", "recovery_required"]
    retry_hint: RetryHint | None = None
    voice_prompt: str | None = None
    attempts_left: int | None = None
    challenge: Challenge | None = Field(default=None, description="Chỉ có khi status = retry")
    voice_challenge_id: str | None = None

    @model_validator(mode="after")
    def demo_cannot_be_verified(self):
        if self.evaluation_mode == "manual_demo" and (
            not self.demo_policy_id or self.status not in {"review", "retry"}
        ):
            raise ValueError("Manual evaluation cannot return an authenticated status")
        if self.evaluation_mode == "standard" and self.demo_policy_id is not None:
            raise ValueError("Standard evaluation has no manual policy")
        if self.demo_complete and (
            self.status != "review"
            or self.evaluation_mode != "manual_demo"
            or not self.demo_policy_id
        ):
            raise ValueError("Demo completion is not an authenticated pass")
        return self


class VoiceResponse(BaseModel):
    status: Literal["pass", "review", "voice_challenge", "deny"]
    voice_prompt: str | None = None
    attempts_left: int | None = None
    voice_challenge_id: str | None = None
    account: AccountReceipt | None = None


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
    retry_hint: Literal["QR_UNREADABLE", "QR_INVALID", "PORTRAIT_UNREADABLE"] | None = None


class IdCardConfirmResponse(BaseModel):
    received: bool = True


class ChallengeResponse(BaseModel):
    token: str = Field(description="Token mới của phiên; token cũ hết hiệu lực")
    expires_at: datetime = Field(description="Hạn mới của token")
    challenge: Challenge


class ErrorResponse(BaseModel):
    error_code: str
    message: str
