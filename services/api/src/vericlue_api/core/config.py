"""Cấu hình API — chỉ đọc từ biến môi trường / file `.env` (xem `.env.example`)."""

from __future__ import annotations

import secrets
from functools import cached_property, lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field, PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from vericlue_api.core.chromapulse_config import load_chromapulse_config
from vericlue_api.core.session_tokens import SessionTokenSigner

if TYPE_CHECKING:
    from vericlue_api.core.report_signing import ReportSigner
    from vericlue_api.core.signing import ResultSigner


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    _mock_session_key: bytes = PrivateAttr(default_factory=lambda: secrets.token_bytes(32))

    app_name: str = "VeriClue API"
    api_cors_origins: str = "http://localhost:3000"
    use_mock_models: bool | Literal["mixed"] = True  # mixed: module có mô hình thật dùng thật
    router_profile: Literal["full", "mvp"] = "full"
    device: str = "cpu"
    lipsync_device: Literal["cpu", "cuda", "auto"] = "cpu"
    models_dir: str = "./models"
    media_dir: str = "./tmp/media"
    data_dir: str = "./data"
    database_url: str = "postgresql+psycopg://localhost/vericlue"
    database_host: str | None = None
    database_port: int = Field(default=5432, ge=1, le=65535)
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None
    postgres_db: str | None = None

    @model_validator(mode="after")
    def database_components(self):
        if self.database_host:
            if not self.postgres_user or self.postgres_password is None or not self.postgres_db:
                raise ValueError(
                    "DATABASE_HOST requires POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB"
                )
            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password.get_secret_value(),
                host=self.database_host,
                port=self.database_port,
                database=self.postgres_db,
            ).render_as_string(hide_password=False)
        return self

    detector_timeout_seconds: float = Field(default=4.0, gt=0, le=4.0)
    detector_queue_size: int = Field(default=3, ge=0, le=32)
    inference_budget_seconds: float = Field(default=4.8, gt=0, le=4.8)
    detector_workers: int = Field(default=9, ge=1, le=32)
    db_lock_timeout_seconds: float = Field(default=2.0, gt=0, le=10.0)

    media_ttl_pass_hours: int = Field(default=24, gt=0)
    media_ttl_review_days: int = Field(default=30, gt=0)
    media_ttl_incomplete_hours: int = Field(default=24, gt=0)
    forensic_ttl_days: int | None = Field(default=None, gt=0)
    media_cleanup_interval_seconds: float = Field(default=300, gt=0)
    # Opt-in encrypted session storage. A random base64-encoded 32-byte master key
    # is mandatory; never fall back to the token/HMAC key or a development constant.
    session_privacy: bool = False
    session_master_key: SecretStr | None = None
    # Demo staff credentials: JSON object {random_token: actor_id}. No client actor header.
    staff_access_tokens: SecretStr | None = None
    require_media_proof: bool = False
    account_enrollment: bool = False
    report_signing_key_path: str | None = None
    result_signing_key_file: str | None = None
    result_issuer: str | None = Field(default=None, pattern=r"^[A-Za-z0-9:/._-]{1,200}$")
    result_audience: str | None = Field(default=None, pattern=r"^[A-Za-z0-9:/._-]{1,200}$")
    result_ttl_seconds: int = Field(default=60, ge=1, le=60)

    @field_validator("report_signing_key_path", mode="before")
    @classmethod
    def blank_disables_report_signing(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @cached_property
    def report_signer(self) -> ReportSigner:
        """Load an explicit report key once; never use session keys or generate a fallback."""
        from vericlue_api.core.errors import ApiError
        from vericlue_api.core.report_signing import ReportSigner
        from vericlue_api.core.signing import load_private_key

        try:
            if not self.report_signing_key_path:
                raise ValueError("Report signing key required")
            return ReportSigner(load_private_key(Path(self.report_signing_key_path)))
        except Exception as exc:
            raise ApiError(
                503, "report_signing_unavailable", "Chưa thể ký hoặc kiểm tra báo cáo lúc này."
            ) from exc

    @field_validator("result_signing_key_file", "result_issuer", "result_audience", mode="before")
    @classmethod
    def blank_disables_result_signing(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @cached_property
    def result_signer(self) -> ResultSigner:
        """Load one configured key per application; no generated/fallback development key."""
        from vericlue_api.core.errors import ApiError
        from vericlue_api.core.signing import ResultSigner, load_private_key

        try:
            if (
                not self.result_signing_key_file
                or not self.result_issuer
                or not self.result_audience
            ):
                raise ValueError("Signing configuration required")
            return ResultSigner(load_private_key(Path(self.result_signing_key_file)))
        except Exception as exc:
            raise ApiError(
                503, "result_signing_unavailable", "Chưa thể cấp kết quả lúc này."
            ) from exc

    @field_validator("use_mock_models", mode="before")
    @classmethod
    def _normalize_mock_mode(cls, value):
        """`MIXED`/` mixed ` cũng chạy, giống registry; giá trị lạ vẫn bị pydantic từ chối."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("forensic_ttl_days", mode="before")
    @classmethod
    def blank_disables_forensic_expiration(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    # Phiên và thử thách (ADR-0011); gia hạn theo ADR-0017 (LIVE-06): POST /challenge.
    session_signing_secret: SecretStr | None = None
    session_ttl_seconds: int = Field(default=300, gt=0)
    challenge_ttl_seconds: int = Field(default=120, gt=0)
    # Giới hạn tổng của một phiên khi gia hạn token (ADR-0017 §2).
    session_max_seconds: int = Field(default=900, gt=0)
    # OTP mô phỏng (FLOW-02): mã 6 số, hạn 2 phút, sai 5 lần thì khóa.
    otp_ttl_seconds: int = 120
    otp_max_attempts: int = 5
    otp_max_sends: int = 3  # số lần gửi mã mỗi phiên
    # Khóa HMAC cho số điện thoại và số CCCD (FLOW-03). Mặc định chỉ để chạy dev; máy demo đặt ID_HMAC_KEY.
    id_hmac_key: SecretStr = SecretStr("dev-only-not-secret")
    # Opt-in identity flow: remote QR/OCR, local SCRFD + LVFace-B via the orchestrator.
    identity_lab_url: str | None = None
    identity_lab_timeout_seconds: float = Field(default=90, gt=0, le=180)
    identity_face_calibration: str | None = None
    identity_account_calibration: str | None = None
    identity_recovery_calibration: str | None = None
    identity_face_from_video: bool = False
    session_face_checks: bool = False
    session_face_models: bool = False
    identity_consistency_required: bool = False
    identity_consistency_calibration: str | None = None
    identity_voice_continuity: bool = False
    identity_voice_calibration: str | None = None
    session_voice_models: bool = False
    voice_runtime_python: str | None = None
    voice_spoof_python: str | None = None
    session_model_timeout_seconds: float = Field(default=30, gt=0, le=90)

    @model_validator(mode="after")
    def consistency_requires_video(self):
        if self.identity_consistency_required and not self.identity_face_from_video:
            raise ValueError("IDENTITY_CONSISTENCY_REQUIRED requires IDENTITY_FACE_FROM_VIDEO")
        if self.identity_voice_continuity and (
            not self.identity_face_from_video or not self.identity_lab_url
        ):
            raise ValueError(
                "IDENTITY_VOICE_CONTINUITY requires video identity and IDENTITY_LAB_URL"
            )
        return self

    max_retries: int = Field(default=2, ge=0, le=2)
    max_upload_mb: int = Field(default=50, ge=1)
    # Total HTTP body, including all files and multipart framing (PLAT-06).
    max_request_mb: int = Field(default=128, ge=1)
    session_create_limit: int = Field(default=3, ge=1, le=1000)
    session_create_window_seconds: int = Field(default=3600, ge=1)
    session_rate_max_clients: int = Field(default=10000, ge=1, le=100000)
    # Để trống = dùng bảng màu trong packages/contracts/chromapulse.json (nguồn chung với web).
    challenge_palette: str = ""

    thresholds_config: str | None = None

    @cached_property
    def session_token_signer(self) -> SessionTokenSigner:
        from vericlue_api.core.errors import ApiError

        key = (
            self.session_signing_secret.get_secret_value().encode("utf-8")
            if self.session_signing_secret is not None
            else b""
        )
        if not key and self.use_mock_models is True:
            key = self._mock_session_key  # Stable even for concurrent first requests.
        if len(key) < 32:
            raise ApiError(503, "security_unavailable", "Dịch vụ xác thực chưa sẵn sàng.")
        return SessionTokenSigner(key)

    @cached_property
    def router_config(self):
        from vericlue_ml.router.config import load_config

        return load_config(self.thresholds_config)

    @property
    def palette(self) -> list[str]:
        override = [c.strip() for c in self.challenge_palette.split(",") if c.strip()]
        return override or list(load_chromapulse_config().palette)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
