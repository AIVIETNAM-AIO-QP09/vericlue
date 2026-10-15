"""Cấu hình API — chỉ đọc từ biến môi trường / file `.env` (xem `.env.example`)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from vericlue_api.core.chromapulse_config import load_chromapulse_config


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VeriClue API"
    api_cors_origins: str = "http://localhost:3000"
    use_mock_models: bool = True
    device: str = "cpu"
    models_dir: str = "./models"
    media_dir: str = "./tmp/media"

    # Phiên và thử thách (ADR-0011). Token HMAC/TTL thật do PLAT-06 cài.
    session_ttl_seconds: int = 300
    challenge_ttl_seconds: int = 120
    max_retries: int = 2
    max_upload_mb: int = 50
    # Để trống = dùng bảng màu trong packages/contracts/chromapulse.json (nguồn chung với web).
    challenge_palette: str = ""

    # TẠM — ROUT-02 thay thế bằng ngưỡng khóa trong ml/configs/thresholds.yaml.
    provisional_threshold_b: float = 0.15
    provisional_threshold_a: float = 0.60

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
