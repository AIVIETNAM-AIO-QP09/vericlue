"""Bounded server-side frame selection; decoder timestamps only, no FPS/seek fallback."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from vericlue_ml.common.result import ErrorCode, Status
from vericlue_ml.presence.landmarks import (
    MAX_EXTRACT_SECONDS,
    MAX_FRAME_PIXELS,
    MAX_VIDEO_FRAMES,
    MAX_VIDEO_MS,
    LandmarkError,
)

MAX_VIDEO_BYTES = 64 * 1024 * 1024
MAX_FRAME_OFFSET_MS = 100  # Provisional sampling tolerance, not a security threshold.
VIEW_SAMPLER_VERSION = "timestamp-nearest@0.1"


@dataclass(frozen=True)
class SelectedFrame:
    target_ms: float
    at_ms: float
    bgr: np.ndarray


def video_sha256(video: Path) -> str:
    """Check local container magic/size before native decoding; never open playlist URLs."""
    if not video.is_file() or not 0 < video.stat().st_size <= MAX_VIDEO_BYTES:
        raise LandmarkError(ErrorCode.E_DECODE)
    with video.open("rb") as handle:
        header = handle.read(12)
        if not (
            header.startswith(b"\x1aE\xdf\xa3")
            or header[4:8] == b"ftyp"
            or (header.startswith(b"RIFF") and header[8:12] == b"AVI ")
        ):
            raise LandmarkError(ErrorCode.E_DECODE)
        handle.seek(0)
        digest, total = hashlib.sha256(), 0
        while block := handle.read(1 << 20):
            total += len(block)
            if total > MAX_VIDEO_BYTES:
                raise LandmarkError(ErrorCode.E_DECODE)
            digest.update(block)
        return digest.hexdigest()


def select_video_frames(video: Path, targets: dict[str, float]) -> dict[str, SelectedFrame]:
    """Keep only three nearest frames in RAM; require a frame within 100 ms of each target."""
    if set(targets) != {"front", "left", "right"}:
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    return _select_frames(video, targets)


def select_frontal_frame(video: Path, target_ms: float) -> SelectedFrame:
    """Select a single server-timed frontal frame, without needing head-turn side views."""
    return _select_frames(video, {"front": target_ms})["front"]


def _select_frames(video: Path, targets: dict[str, float]) -> dict[str, SelectedFrame]:
    if (
        len(targets) not in (1, 3)
        or any(
            isinstance(t, bool)
            or not isinstance(t, (int, float))
            or not math.isfinite(t)
            or not 0 <= t <= MAX_VIDEO_MS
            for t in targets.values()
        )
        or len(set(targets.values())) != len(targets)
    ):
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    video_sha256(video)
    import cv2

    capture = cv2.VideoCapture(str(video))
    previous, started = -1.0, perf_counter()
    picked: dict[str, SelectedFrame] = {}
    end_ms = min(MAX_VIDEO_MS, max(targets.values()) + MAX_FRAME_OFFSET_MS)
    try:
        if not capture.isOpened():
            raise LandmarkError(ErrorCode.E_DECODE)
        for _ in range(MAX_VIDEO_FRAMES):
            ok, frame = capture.read()
            if not ok:
                break
            if (
                not isinstance(frame, np.ndarray)
                or frame.ndim != 3
                or frame.shape[2] != 3
                or frame.dtype != np.uint8
                or min(frame.shape[:2]) <= 0
                or frame.shape[0] * frame.shape[1] > MAX_FRAME_PIXELS
            ):
                raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
            at_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            if (
                not math.isfinite(at_ms)
                or at_ms < 0
                or at_ms <= previous
                or (previous < 0 and at_ms > 200)
            ):
                raise LandmarkError(ErrorCode.E_DECODE)
            previous = at_ms
            if perf_counter() - started > MAX_EXTRACT_SECONDS:
                raise LandmarkError(ErrorCode.E_TIMEOUT)
            if at_ms > end_ms:
                break
            for role, target in targets.items():
                distance = abs(at_ms - target)
                old = picked.get(role)
                if distance <= MAX_FRAME_OFFSET_MS and (
                    old is None or distance < abs(old.at_ms - target)
                ):
                    picked[role] = SelectedFrame(target, at_ms, frame.copy())
        else:
            raise LandmarkError(ErrorCode.E_TIMEOUT)
    finally:
        capture.release()
    if set(picked) != set(targets):
        raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
    if len({frame.at_ms for frame in picked.values()}) != len(targets):
        raise LandmarkError(ErrorCode.E_INTEGRITY, Status.DEGRADED)
    return picked
