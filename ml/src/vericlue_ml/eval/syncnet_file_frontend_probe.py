"""Probe frontend ngoại tuyến trên khung hình nguyên gốc của file video.

This is the file-decoder counterpart of the RAM/JPEG diagnostic, with distinct
provenance. It preserves voice.syncnet._read_windows target/nearest-PTS/EOF
selection semantics but aligns ALL frames for full-video bias history. It does
not rewrite video/audio, transcode JPEGs, seek by FPS, select prompts, optimize
offsets, load models or activate a production frontend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Integral, Real
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from vericlue_ml.common.result import ErrorCode
from vericlue_ml.eval.syncnet_frontend_probe import _selected_box
from vericlue_ml.face.pad import ScrfdFaceFinder
from vericlue_ml.voice.syncnet import (
    MAX_RESAMPLE_ERROR_SECONDS,
    MAX_SYNC_WINDOWS,
    SYNCNET_FPS,
    SYNCNET_FRAMES,
    SYNCNET_IMAGE_SIZE,
    SyncNetError,
)

if TYPE_CHECKING:
    from vericlue_ml.eval.syncnet_frontend import SyncNetFrontendCandidate
    from vericlue_ml.voice.landmarks106 import Landmark106Provider

FILE_PROBE_VERSION = "original-file-opencv-pts-v1"
MAX_FILE_SECONDS = 21.0
MAX_FILE_FRAMES = 1200
# Same decoded-pixel bound as face.gend and presence.landmarks; never resize to fit.
MAX_FILE_FRAME_PIXELS = 1920 * 1080


@dataclass(frozen=True)
class FileFrontendProbeResult:
    """Bounded transient RGB windows, aggregate counts and non-identifying provenance."""

    windows: list[list[np.ndarray]] = field(repr=False)
    counts: dict[str, int]
    provenance: dict[str, str | float]


def _targets(starts: list[int], audio_offset_s: float) -> tuple[tuple[int, ...], list[int], float]:
    if not isinstance(starts, (list, tuple)) or not 0 < len(starts) <= MAX_SYNC_WINDOWS:
        raise SyncNetError("Expected a bounded nonempty list of predeclared window starts")
    if any(
        isinstance(start, bool)
        or not isinstance(start, Integral)
        or not 0 <= start <= MAX_FILE_SECONDS * SYNCNET_FPS
        for start in starts
    ):
        raise SyncNetError("Window starts must be bounded nonnegative integers")
    if (
        isinstance(audio_offset_s, bool)
        or not isinstance(audio_offset_s, Real)
        or not math.isfinite(audio_offset_s)
    ):
        raise SyncNetError("Audio origin offset must be finite", ErrorCode.E_DECODE)
    requested = tuple(int(start) for start in starts)
    targets = sorted(
        {position for start in requested for position in range(start, start + SYNCNET_FRAMES)}
    )
    offset = float(audio_offset_s)
    if (
        targets[0] / SYNCNET_FPS + offset < 0
        or targets[-1] / SYNCNET_FPS + offset > MAX_FILE_SECONDS
    ):
        raise SyncNetError("Invalid original-file video bounds", ErrorCode.E_DECODE)
    return requested, targets, offset


def prepare_file_frontend_probe(
    video: Path,
    starts: list[int],
    *,
    audio_offset_s: float = 0,
    finder: ScrfdFaceFinder,
    landmark_provider: Landmark106Provider,
    frontend: SyncNetFrontendCandidate,
) -> FileFrontendProbeResult:
    """Stream original decoded frames; preserve predeclared audio-clock targets.

    Inject finder(512, scale=128, swap_rb=True), RGB Landmark106Provider and
    float32 frontend. At most 21 seconds/1200 frames/1920*1080 pixels per frame
    are accepted. Every frame must succeed, including the unused tail. Only
    <=64 selected crops plus a current/previous working crop are retained.
    Original pixels receive channel reversal only before landmark alignment.
    Returned windows are inputs, not evidence of accuracy or runtime readiness.
    """
    requested, targets, offset = _targets(starts, audio_offset_s)
    if (
        getattr(finder, "_input_size", None) != 512
        or getattr(finder, "_scale", None) != 128.0
        or getattr(finder, "_swap_rb", None) is not True
        or getattr(landmark_provider, "color_order", None) != "rgb"
        or getattr(frontend, "warp_dtype", None) != "float32"
    ):
        raise SyncNetError("Expected explicit 512/RGB/128 detector and RGB/float32 frontend")
    import cv2

    capture = cv2.VideoCapture(str(video))
    selected: dict[int, np.ndarray] = {}
    selected_frames: set[int] = set()
    previous: tuple[float, np.ndarray, int] | None = None
    cursor = 0
    processed = 0

    def remember(position: int, candidate: tuple[float, np.ndarray, int]) -> None:
        timestamp, crop, index = candidate
        if abs(timestamp - (position / SYNCNET_FPS + offset)) > MAX_RESAMPLE_ERROR_SECONDS + 1e-6:
            raise SyncNetError(
                "Video timestamp gap is too large", ErrorCode.E_LOW_QUALITY, "degraded"
            )
        selected[position] = crop
        selected_frames.add(index)

    try:
        if not capture.isOpened():
            raise SyncNetError("Undecodable video", ErrorCode.E_DECODE)
        frontend.reset()
        while True:
            ok, image = capture.read()
            if not ok:
                # Same EOF fallback as _read_windows; never invent extra frames.
                while previous is not None and cursor < len(targets):
                    remember(targets[cursor], previous)
                    cursor += 1
                if cursor < len(targets):
                    raise SyncNetError("Missing aligned video", ErrorCode.E_DECODE)
                break
            if processed >= MAX_FILE_FRAMES:
                raise SyncNetError("Too many original video frames", ErrorCode.E_DECODE)
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if (
                not math.isfinite(timestamp)
                or timestamp < 0
                or (previous is not None and timestamp <= previous[0])
            ):
                raise SyncNetError(
                    "Missing or non-monotonic presentation timestamps",
                    ErrorCode.E_LOW_QUALITY,
                    "degraded",
                )
            if timestamp > MAX_FILE_SECONDS:
                raise SyncNetError("Video timestamp exceeds probe limit", ErrorCode.E_DECODE)
            if (
                not isinstance(image, np.ndarray)
                or image.dtype != np.uint8
                or image.ndim != 3
                or image.shape[2] != 3
                or min(image.shape[:2]) <= 0
                or image.shape[0] * image.shape[1] > MAX_FILE_FRAME_PIXELS
            ):
                raise SyncNetError("Invalid original decoded frame", ErrorCode.E_DECODE)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            bbox = _selected_box(finder.find(rgb))
            landmarks = landmark_provider.predict(rgb, bbox)
            if (
                not isinstance(landmarks, np.ndarray)
                or landmarks.dtype != np.float32
                or landmarks.shape != (106, 2)
                or not np.isfinite(landmarks).all()
            ):
                raise SyncNetError("Invalid landmark output")
            aligned = frontend.align_frame(rgb, landmarks, frame_index=processed)
            if (
                not isinstance(aligned, np.ndarray)
                or aligned.dtype != np.uint8
                or aligned.shape != (SYNCNET_IMAGE_SIZE, SYNCNET_IMAGE_SIZE, 3)
            ):
                raise SyncNetError("Invalid aligned RGB square")
            current = (timestamp, aligned, processed)
            processed += 1
            while cursor < len(targets) and targets[cursor] / SYNCNET_FPS + offset <= timestamp:
                target_s = targets[cursor] / SYNCNET_FPS + offset
                candidate = current
                if previous is not None and abs(target_s - previous[0]) <= abs(
                    timestamp - target_s
                ):
                    candidate = previous
                remember(targets[cursor], candidate)
                cursor += 1
            # Unlike baseline's selected-only decoder, continue through the tail
            # to preserve full-video state and detect failures in unused frames.
            previous = current
        windows = [
            [selected[position] for position in range(start, start + SYNCNET_FRAMES)]
            for start in requested
        ]
        return FileFrontendProbeResult(
            windows,
            {
                "decoded_frames": processed,
                "aligned_frames": processed,
                "selected_frames": len(selected_frames),
                "windows": len(windows),
            },
            {
                "pipeline": FILE_PROBE_VERSION,
                "selection_reference": "voice.syncnet._read_windows",
                "audio_offset_s": offset,
            },
        )
    finally:
        capture.release()
