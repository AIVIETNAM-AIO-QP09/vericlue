"""Private QR/OCR runtime bridge; face matching runs locally through the ML orchestrator."""

from __future__ import annotations

import httpx

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError


class IdentityRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _post(self, endpoint: str, images: dict[str, bytes]) -> dict:
        try:
            with httpx.Client(
                timeout=self.settings.identity_lab_timeout_seconds, trust_env=False
            ) as client:
                response = client.post(
                    self.settings.identity_lab_url.rstrip("/") + endpoint,
                    files={
                        name: (name + ".jpg", value, "application/octet-stream")
                        for name, value in images.items()
                    },
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("Invalid runtime response")
                return body
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError(
                503, "identity_unavailable", "Không thể xử lý ảnh lúc này. Vui lòng thử lại."
            ) from exc

    def scan(self, front: bytes, back: bytes) -> dict:
        return self._post("/internal/id-card", {"front": front, "back": back})
