"""Đọc `packages/contracts/chromapulse.json` — nguồn duy nhất của bảng màu, nhịp và giới hạn an toàn.

Web (`apps/web/src/lib/capture/chromapulse/`) đọc cùng file này. Khi đóng gói (Docker, PLAT-05),
sao chép file vào ảnh và trỏ biến môi trường `CHROMAPULSE_CONFIG` tới nó.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[5] / "packages" / "contracts" / "chromapulse.json"


@dataclass(frozen=True)
class ChromaPulseConfig:
    palette: tuple[str, ...]
    baseline_color: str
    steps: int
    baseline_ms: int
    tail_ms: int
    hold_min_ms: int
    hold_max_ms: int
    transition_ms: int
    max_changes_per_second: float
    max_luminance_spread: float
    max_red_share: float


def config_path() -> Path:
    return Path(os.environ.get("CHROMAPULSE_CONFIG", DEFAULT_PATH))


@lru_cache
def load_chromapulse_config() -> ChromaPulseConfig:
    path = config_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy file cấu hình ChromaPulse. Đã thử: {path}. "
            "Đặt biến môi trường CHROMAPULSE_CONFIG trỏ tới packages/contracts/chromapulse.json "
            "(ví dụ trong ảnh Docker, nơi cấu trúc thư mục khác repo)."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    limits = raw["limits"]
    return ChromaPulseConfig(
        palette=tuple(raw["palette"]),
        baseline_color=raw["baseline_color"],
        steps=raw["steps"],
        baseline_ms=raw["baseline_ms"],
        tail_ms=raw["tail_ms"],
        hold_min_ms=raw["hold_ms"]["min"],
        hold_max_ms=raw["hold_ms"]["max"],
        transition_ms=raw["transition_ms"],
        max_changes_per_second=limits["max_changes_per_second"],
        max_luminance_spread=limits["max_luminance_spread"],
        max_red_share=limits["max_red_share"],
    )
