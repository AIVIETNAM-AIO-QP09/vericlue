"""Cấu hình API — chỉ đọc từ biến môi trường / file `.env` (xem `.env.example`)."""

from __future__ import annotations

import secrets
from functools import cached_property, lru_cache
from typing import Literal

from pydantic import Field, PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from vericlue_api.core.chromapulse_config import load_chromapulse_config
from vericlue_api.core.session_tokens import SessionTokenSigner


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
    # Opt-in bridge to the local OCR/AdaFace runtime. Other detectors keep their own mode.
    identity_lab_url: str | None = None
    identity_lab_timeout_seconds: float = Field(default=90, gt=0, le=180)
    identity_face_threshold: float = Field(default=0.40, ge=-1, le=1, allow_inf_nan=False)
    max_retries: int = Field(default=2, ge=0, le=2)
    max_upload_mb: int = 50
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
