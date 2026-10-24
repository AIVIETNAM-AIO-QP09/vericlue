"""Private OCR/face runtime bridge; never sends scores to the citizen API."""

from __future__ import annotations

import math
from pathlib import Path
from time import perf_counter

import httpx

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_ml.common.result import ErrorCode, Gate, Module, ModuleResult, Status


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

    def match(self, reference: Path | None, images: list[Path]) -> ModuleResult:
        started = perf_counter()
        threshold = self.settings.identity_face_threshold
        result = ModuleResult(
            module=Module.FACE_MATCH,
            model_version="adaface-ir18-context@identity-lab-v1",
            status=Status.ERROR,
            error_code=ErrorCode.E_INTERNAL,
            gate=Gate.UNCLEAR,
            latency_ms=0,
            quality={"threshold": threshold, "provisional": True},
        )
        if reference is None or not images:
            return result.model_copy(update={"error_code": ErrorCode.E_NO_FACE})
        try:
            # First server-received neutral still; never choose the highest scoring frame.
            body = self._post(
                "/internal/face-match",
                {"reference": reference.read_bytes(), "selfie": images[0].read_bytes()},
            )
            score = body.get("cosine_similarity")
            if (
                body.get("status") != "ok"
                or type(score) not in (int, float)
                or not math.isfinite(score)
                or not -1 <= score <= 1
            ):
                return result.model_copy(
                    update={"status": Status.DEGRADED, "error_code": ErrorCode.E_LOW_QUALITY}
                )
            return result.model_copy(
                update={
                    "status": Status.OK,
                    "error_code": None,
                    "score": score,
                    "gate": Gate.PASS if score >= threshold else Gate.FAIL,
                    "latency_ms": (perf_counter() - started) * 1000,
                }
            )
        except (ApiError, OSError):
            return result
