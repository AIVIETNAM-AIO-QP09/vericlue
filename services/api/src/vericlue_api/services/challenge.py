"""Bộ sinh thử thách màu (ChromaPulse). Bảng màu lấy từ cấu hình, không cứng trong schema (ADR-0011).

Ràng buộc đã có test: đúng 8 màu, hai màu liền kề khác nhau, <= 2,5 lần đổi màu/giây,
chênh độ chói tương đối <= 0,064, không màu nào có R/(R+G+B) >= 0,8.
"""

from __future__ import annotations

import random
import secrets
from datetime import UTC, datetime, timedelta

from vericlue_api.core.chromapulse_config import load_chromapulse_config
from vericlue_api.core.config import Settings
from vericlue_api.schemas.session import Challenge, ColorStep, DotPoint

# Bảng màu, nhịp và giới hạn lấy từ packages/contracts/chromapulse.json (nguồn chung với web).
_CFG = load_chromapulse_config()
STEPS = _CFG.steps
BASELINE_MS = _CFG.baseline_ms
HOLD_RANGE_MS = (_CFG.hold_min_ms, _CFG.hold_max_ms)
TRANSITION_MS = _CFG.transition_ms
MAX_LUMINANCE_SPREAD = _CFG.max_luminance_spread
MAX_RED_SHARE = _CFG.max_red_share
CAPTURE_POINTS = 2

# Đường chấm sáng (LIVE-01, lớp ② của ADR-0016): khoảng 6 giây, chấm đi thẳng giữa các điểm.
DOT_POINTS = 7
DOT_STEP_MS = 1000
DOT_MARGIN = 0.15  # tránh mép màn hình, tai thỏ, thanh điều hướng
DOT_MIN_JUMP = 0.25  # hai điểm liền kề đủ xa để mắt phải đưa theo


def relative_luminance(rgb: str) -> float:
    """Độ chói tương đối theo WCAG."""
    channels = [int(rgb[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def red_share(rgb: str) -> float:
    r, g, b = (int(rgb[i : i + 2], 16) for i in (1, 3, 5))
    return r / (r + g + b) if r + g + b else 0.0


def validate_palette(palette: list[str]) -> None:
    """Bảng màu cấu hình phải giữ các giới hạn an toàn của ADR-0011; sai thì từ chối khởi tạo."""
    if len(palette) < 2:
        raise ValueError("Bảng màu cần ít nhất 2 màu")
    lum = [relative_luminance(c) for c in palette]
    if max(lum) - min(lum) > MAX_LUMINANCE_SPREAD:
        raise ValueError(f"Bảng màu chênh độ chói quá {MAX_LUMINANCE_SPREAD}")
    if any(red_share(c) >= MAX_RED_SHARE for c in palette):
        raise ValueError(f"Bảng màu có màu với R/(R+G+B) >= {MAX_RED_SHARE}")


def generate_challenge(
    settings: Settings, rng: random.Random | None = None, now: datetime | None = None
) -> Challenge:
    rng = rng or random.SystemRandom()
    now = now or datetime.now(UTC)
    palette = settings.palette
    validate_palette(palette)

    sequence: list[ColorStep] = []
    previous: str | None = None
    for _ in range(STEPS):
        color = rng.choice([c for c in palette if c != previous])
        sequence.append(
            ColorStep(rgb=color, hold_ms=rng.randint(*HOLD_RANGE_MS), transition_ms=TRANSITION_MS)
        )
        previous = color

    # Thời điểm chụp ảnh chất lượng cao: giữa một số bước (không phải bước đầu/cuối).
    starts, t = [], BASELINE_MS
    for step in sequence:
        starts.append(t)
        t += step.hold_ms + step.transition_ms
    picks = sorted(rng.sample(range(1, STEPS - 1), CAPTURE_POINTS))
    capture_at = [starts[i] + sequence[i].hold_ms // 2 for i in picks]

    return Challenge(
        challenge_id=f"ch_{secrets.token_hex(8)}",
        baseline_ms=BASELINE_MS,
        color_sequence=sequence,
        capture_at_ms=capture_at,
        expires_at=now + timedelta(seconds=settings.challenge_ttl_seconds),
        turn_order=rng.sample(["left", "right"], 2),
        dot_path=generate_dot_path(rng),
    )


def generate_dot_path(rng: random.Random) -> list[DotPoint]:
    """Điểm ngẫu nhiên trong vùng an toàn, mỗi điểm cách điểm trước ít nhất DOT_MIN_JUMP."""
    points: list[DotPoint] = []
    lo, hi = DOT_MARGIN, 1 - DOT_MARGIN
    while len(points) < DOT_POINTS:
        x, y = round(rng.uniform(lo, hi), 3), round(rng.uniform(lo, hi), 3)
        if points and ((x - points[-1].x) ** 2 + (y - points[-1].y) ** 2) ** 0.5 < DOT_MIN_JUMP:
            continue
        points.append(DotPoint(t_ms=len(points) * DOT_STEP_MS, x=x, y=y))
    return points
