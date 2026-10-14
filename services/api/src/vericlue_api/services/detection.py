"""Chạy các bộ phát hiện (tuần tự, TẠM — PLAT-08 thay bằng orchestrator song song)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Module, ModuleResult, Status
from vericlue_ml.registry import get_detector


def run_detectors(
    modules: Iterable[Module],
    *,
    session_id: str | None,
    scenario: str,
    images: list[Path] | None = None,
    video: Path | None = None,
    audio: Path | None = None,
    signals: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[Module, ModuleResult]:
    """Một detector ném ngoại lệ thì thành `status=error`, không bao giờ thành 'đạt'."""
    inp = DetectorInput(
        session_id=session_id,
        images=images or [],
        video=video,
        audio=audio,
        signals=signals or {},
        metadata={"scenario": scenario, **(extra_metadata or {})},
    )
    out: dict[Module, ModuleResult] = {}
    for module in modules:
        try:
            out[module] = get_detector(module).predict(inp)
        except Exception:  # noqa: BLE001 - mọi lỗi của detector đều phải thành kết quả 'error'
            out[module] = ModuleResult(
                module=module,
                model_version="unavailable",
                status=Status.ERROR,
                error_code=ErrorCode.E_INTERNAL,
                latency_ms=0.0,
            )
    return out
