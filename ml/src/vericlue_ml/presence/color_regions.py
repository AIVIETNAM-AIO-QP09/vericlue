"""Server color measurements, matching this repo's CAP-03 regions.ts definitions.

Landmark indices, inset, background guard, luma mask and median are ported from
apps/web/src/lib/capture/chromapulse/regions.ts, not from an external detector.
RGB statistics are not skin segmentation or evidence of physical face depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from vericlue_ml.presence.landmarks import FaceObservationReader

REGION_LANDMARKS = {
    "forehead": (10, 109, 338, 67, 297, 103, 332, 151),
    "left_cheek": (50, 101, 118, 117, 123, 205, 187),
    "right_cheek": (280, 330, 347, 346, 352, 425, 411),
    "nose": (1, 4, 5, 6, 195, 197, 98, 327),
    "chin": (152, 175, 199, 200, 377, 148, 176),
}


@dataclass(frozen=True)
class RegionStat:
    rgb_all: tuple[float, float, float] | None
    rgb_trim: tuple[float, float, float] | None
    pixels: int
    excluded_fraction: float


@dataclass(frozen=True)
class ColorObservation:
    at_ms: float
    face_count: int
    regions: dict[str, RegionStat] = field(default_factory=dict)


def summarize_pixels(pixels: np.ndarray) -> RegionStat:
    """Median RGB before/after excluding luma <=55 or >=200, as in CAP-03."""
    pixels = np.asarray(pixels).reshape(-1, 3)
    if not len(pixels):
        return RegionStat(None, None, 0, 0.0)
    luma = pixels @ np.array([0.299, 0.587, 0.114])
    kept = pixels[(luma > 55) & (luma < 200)]
    return RegionStat(
        tuple(float(v) for v in np.median(pixels, axis=0)),
        tuple(float(v) for v in np.median(kept, axis=0)) if len(kept) else None,
        len(pixels),
        1 - len(kept) / len(pixels),
    )


def _rect(lo: np.ndarray, hi: np.ndarray, width: int, height: int):
    # JS Math.round for nonnegative/clamped bounds; avoid numpy's ties-to-even.
    x0, y0 = np.maximum(0, np.floor(lo + 0.5)).astype(int)
    x1, y1 = np.minimum([width, height], np.floor(hi + 0.5)).astype(int)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def color_observation(result: Any, rgb: np.ndarray, at_ms: float) -> ColorObservation:
    """Extract five inset skin rectangles and pooled background corners in RAM."""
    count = len(result.face_landmarks)
    if count != 1:
        return ColorObservation(at_ms, count)
    points = np.asarray([(p.x, p.y) for p in result.face_landmarks[0]], dtype=float)
    if points.shape != (478, 2) or not np.isfinite(points).all():
        return ColorObservation(at_ms, count)
    height, width = rgb.shape[:2]
    points *= [width, height]
    regions = {}
    for name, indices in REGION_LANDMARKS.items():
        selected = points[list(indices)]
        lo, hi = selected.min(axis=0), selected.max(axis=0)
        inset = (hi - lo) * 0.2
        rect = _rect(lo + inset, hi - inset, width, height)
        if rect is not None:
            x0, y0, x1, y1 = rect
            regions[name] = summarize_pixels(rgb[y0:y1, x0:x1])
    lo, hi = points.min(axis=0), points.max(axis=0)
    margin = (hi - lo) * 0.1
    lo, hi = lo - margin, hi + margin
    size = int(np.floor(width * 0.12 + 0.5))
    buffers = []
    for left in (0, width - size):
        rect = _rect(np.array([left, 0]), np.array([left + size, size]), width, height)
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        if x0 < hi[0] and lo[0] < x1 and y0 < hi[1] and lo[1] < y1:
            continue
        buffers.append(rgb[y0:y1, x0:x1].reshape(-1, 3))
    regions["background"] = summarize_pixels(
        np.concatenate(buffers) if buffers else np.empty((0, 3))
    )
    return ColorObservation(at_ms, count, regions)


class ColorObservationReader:
    """Reuse the gaze/head landmarker and its bounded decoder; no new checkpoint."""

    def __init__(self, reader: FaceObservationReader | None = None) -> None:
        self.reader = reader if reader is not None else FaceObservationReader()

    def preload(self, **kwargs) -> None:
        self.reader.preload(**kwargs)

    def extract(self, video: Path, *, start_ms: float, end_ms: float) -> list[ColorObservation]:
        return self.reader.extract_measurements(
            video,
            start_ms=start_ms,
            end_ms=end_ms,
            observer=lambda frame, time: self.observe(frame, at_ms=time),
        )

    def observe(self, frame: np.ndarray, *, at_ms: float) -> ColorObservation:
        """Measure a validated BGR frame; retain no pixels after this call."""
        return self.reader.measure(
            frame, at_ms=at_ms, transform=lambda result, rgb: color_observation(result, rgb, at_ms)
        )

    def close(self) -> None:
        self.reader.close()
