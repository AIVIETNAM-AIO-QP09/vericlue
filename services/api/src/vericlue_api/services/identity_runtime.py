"""One application-owned QR/portrait scanner; no HTTP bridge or OCR fallback."""

from __future__ import annotations

from threading import Lock
from typing import Any

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError


class IdentityRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._scanner: Any = None
        self._initializing = Lock()

    def _create_scanner(self):
        from vericlue_api.services.card_scanner import CardScanner

        return CardScanner(models_dir=self.settings.models_dir, device=self.settings.device)

    def preload(self) -> None:
        """Load once on demand, or explicitly before starting the demo server."""
        with self._initializing:
            if self._scanner is not None:
                return
            try:
                scanner = self._create_scanner()
                scanner.preload()
            except Exception:
                raise ApiError(
                    503, "identity_unavailable", "Dịch vụ đọc thẻ chưa sẵn sàng."
                ) from None
            self._scanner = scanner

    def scan(self, front: bytes, back: bytes | None) -> dict:
        """Read uploaded images locally; only sanitized errors leave this boundary."""
        self.preload()
        from vericlue_api.services.card_scanner import InputError

        try:
            return self._scanner.scan(front, back)
        except InputError:
            raise ApiError(
                422, "invalid_id_card", "Ảnh thẻ chưa phù hợp. Vui lòng chụp lại."
            ) from None
        except Exception:
            raise ApiError(
                503, "identity_unavailable", "Không thể xử lý ảnh lúc này. Vui lòng thử lại."
            ) from None
