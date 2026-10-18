"""FOR-01 — chia đoạn và gộp khoảng nghi giả (thuần tính toán, không phụ thuộc mô hình).

ADR-0008: đoạn 2–3 giây chồng lấn 50%; đoạn nghi giả ghi thành KHOẢNG ±1 giây, không ghi mốc chính xác
tới từng khung.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

# Hằng số có tên (ADR-0008, thẻ FOR-01). Không nằm trong thresholds.yaml.
SEGMENT_SECONDS = 3.0
SEGMENT_OVERLAP = 0.5  # chồng lấn 50% → bước nhảy 1,5 giây
INTERVAL_MARGIN_SECONDS = 1.0  # mở rộng ±1 giây quanh nhóm đoạn nghi giả
# Phần đuôi ngắn hơn mức này (giây) không đủ để lập thêm một đoạn riêng.
MIN_TAIL_SECONDS = 0.5


def plan_segments(
    duration_s: float,
    segment_s: float = SEGMENT_SECONDS,
    overlap: float = SEGMENT_OVERLAP,
) -> list[tuple[float, float]]:
    """Các đoạn (t_start, t_end) phủ kín [0, duration_s], chồng lấn theo `overlap`.

    File ngắn hơn một đoạn: một đoạn duy nhất bằng cả file. Phần đuôi còn dư ít nhất
    MIN_TAIL_SECONDS thì thêm một đoạn neo vào cuối file (chồng lấn nhiều hơn 50% với đoạn trước).
    """
    if not duration_s or not math.isfinite(duration_s) or duration_s <= 0:
        return []
    if not 0 <= overlap < 1:
        raise ValueError("overlap phải thuộc [0, 1)")
    if duration_s <= segment_s:
        return [(0.0, round(duration_s, 3))]
    hop = segment_s * (1 - overlap)
    segments: list[tuple[float, float]] = []
    start = 0.0
    while start + segment_s <= duration_s + 1e-9:
        segments.append((round(start, 3), round(start + segment_s, 3)))
        start += hop
    covered = segments[-1][1]
    if duration_s - covered >= MIN_TAIL_SECONDS:
        segments.append((round(duration_s - segment_s, 3), round(duration_s, 3)))
    return segments


def merge_flagged(
    segments: Sequence[tuple[float, float]],
    flagged: Sequence[bool],
    duration_s: float,
    margin_s: float = INTERVAL_MARGIN_SECONDS,
) -> list[tuple[float, float, list[int]]]:
    """Gộp các đoạn LIỀN KỀ bị đánh dấu thành khoảng nghi giả, mở rộng ±margin_s.

    Trả về danh sách (t_start, t_end, chỉ số đoạn) theo thứ tự thời gian. Hai khoảng sau khi mở rộng
    mà chạm hoặc chồng nhau thì gộp tiếp (kết quả không bao giờ chồng nhau). Khoảng được cắt vào
    [0, duration_s]. Đoạn không bị đánh dấu (kể cả `not_applicable`) không bao giờ tạo khoảng.
    """
    if len(segments) != len(flagged):
        raise ValueError("segments và flagged phải cùng độ dài")
    groups: list[list[int]] = []
    for index, is_flagged in enumerate(flagged):
        if not is_flagged:
            continue
        if groups and groups[-1][-1] == index - 1:
            groups[-1].append(index)
        else:
            groups.append([index])

    expanded: list[tuple[float, float, list[int]]] = []
    for group in groups:
        start = max(0.0, segments[group[0]][0] - margin_s)
        end = min(float(duration_s), segments[group[-1]][1] + margin_s)
        if expanded and start <= expanded[-1][1]:
            previous = expanded[-1]
            expanded[-1] = (previous[0], max(previous[1], end), previous[2] + group)
        else:
            expanded.append((start, end, list(group)))
    return [(round(a, 3), round(b, 3), indices) for a, b, indices in expanded]
