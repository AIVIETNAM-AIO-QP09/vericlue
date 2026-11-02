"""Probe frontend SyncNet ngoại tuyến, toàn video, cửa sổ thời gian định trước.

Only prepares bounded in-memory RGB windows and aggregate counts. No audio
rewriting, model loading, prompt selection, offset search, calibration or
runtime activation occurs here. The caller owns all injected components and
must record their versions separately; these crops establish no readiness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Integral
from typing import TYPE_CHECKING

import numpy as np

from vericlue_ml.common.av_recording import AVRecording
from vericlue_ml.common.result import ErrorCode
from vericlue_ml.face.pad import SECOND_FACE_AREA_RATIO, FaceBox, ScrfdFaceFinder
from vericlue_ml.voice.av_lipsync import validate_recording
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


@dataclass(frozen=True)
class FrontendProbeResult:
    """Transient model inputs; only counts are suitable for an aggregate report."""

    windows: list[list[np.ndarray]] = field(repr=False)
    counts: dict[str, int]


def _selected_indices(
    recording: AVRecording, starts: list[int]
) -> tuple[tuple[int, ...], dict[int, int]]:
    if not isinstance(starts, (list, tuple)) or not 0 < len(starts) <= MAX_SYNC_WINDOWS:
        raise SyncNetError("Expected a bounded, predeclared nonempty list of window starts")
    if any(
        isinstance(start, bool) or not isinstance(start, Integral) or start < 0 for start in starts
    ):
        raise SyncNetError("Window starts must be nonnegative integers")
    requested = tuple(int(start) for start in starts)
    times = np.array([frame.at_s for frame in recording.frames])
    last_position = math.floor((times[-1] + MAX_RESAMPLE_ERROR_SECONDS + 1e-6) * SYNCNET_FPS)
    if any(start + SYNCNET_FRAMES - 1 > last_position for start in requested):
        raise SyncNetError(
            "Window exceeds bounded original video clock", ErrorCode.E_LOW_QUALITY, "degraded"
        )
    selected = {}
    # Identical arithmetic to voice.av_lipsync.read_ram_windows, including its
    # earlier-frame tie break and 1e-6 timestamp epsilon. Keep baseline untouched:
    # that helper combines selection with JPEG decoding and bbox-only cropping.
    for position in sorted(
        {p for start in requested for p in range(start, start + SYNCNET_FRAMES)}
    ):
        target = position / SYNCNET_FPS
        after = min(int(np.searchsorted(times, target)), len(times) - 1)
        before = max(0, after - 1)
        index = min((before, after), key=lambda i: abs(times[i] - target))
        if abs(times[index] - target) > MAX_RESAMPLE_ERROR_SECONDS + 1e-6:
            raise SyncNetError(
                "Missing aligned video timestamp", ErrorCode.E_LOW_QUALITY, "degraded"
            )
        selected[position] = index
    return requested, selected


def _selected_box(faces: list[FaceBox]) -> np.ndarray:
    if not faces:
        raise SyncNetError("No face", ErrorCode.E_NO_FACE, "not_applicable")
    for box in faces:
        coordinates = np.array([box.x1, box.y1, box.x2, box.y2], dtype=np.float64)
        if not np.isfinite(coordinates).all() or box.x2 <= box.x1 or box.y2 <= box.y1:
            raise SyncNetError("Invalid face geometry", ErrorCode.E_LOW_QUALITY, "degraded")
    ordered = sorted(faces, key=lambda box: box.area, reverse=True)
    if len(ordered) > 1 and ordered[1].area >= SECOND_FACE_AREA_RATIO * ordered[0].area:
        raise SyncNetError("Ambiguous speaker", ErrorCode.E_MULTI_FACE, "degraded")
    box = ordered[0]
    # SCRFD tensors are float32; preserve that scalar precision in the landmark
    # crop math instead of promoting returned Python floats to float64 first.
    with np.errstate(over="ignore", invalid="ignore"):
        selected = np.array([box.x1, box.y1, box.x2, box.y2], dtype=np.float32)
    if not np.isfinite(selected).all() or np.any(selected[2:] <= selected[:2]):
        raise SyncNetError("Invalid float32 face geometry", ErrorCode.E_LOW_QUALITY, "degraded")
    return selected


def prepare_frontend_probe(
    recording: AVRecording,
    starts: list[int],
    *,
    finder: ScrfdFaceFinder,
    landmark_provider: Landmark106Provider,
    frontend: SyncNetFrontendCandidate,
) -> FrontendProbeResult:
    """Align every original JPEG, retaining at most four sixteen-frame windows.

    Required injected variant: finder(input_size=512, scale=128, swap_rb=True),
    Landmark106Provider(color_order="rgb"), frontend(warp_dtype="float32").
    The caller provides already-loaded components; this function only calls
    find/predict/align_frame. Full-video smoothing is reset once at entry.
    Every chronological frame, including unused preroll/tail, must succeed.
    PTS selection is precomputed solely to bound retained crops to <=64; it
    never skips detection, landmarks or alignment on any decoded frame.
    """
    validate_recording(recording)
    requested, selected = _selected_indices(recording, starts)
    if (
        getattr(finder, "_input_size", None) != 512
        or getattr(finder, "_scale", None) != 128.0
        or getattr(finder, "_swap_rb", None) is not True
        or getattr(landmark_provider, "color_order", None) != "rgb"
        or getattr(frontend, "warp_dtype", None) != "float32"
    ):
        raise SyncNetError("Expected explicit 512/RGB/128 detector and RGB/float32 frontend")
    import cv2

    needed = set(selected.values())
    retained: dict[int, np.ndarray] = {}
    frontend.reset()
    for index, frame in enumerate(recording.frames):
        if not frame.jpeg:
            raise SyncNetError("Invalid JPEG frame", ErrorCode.E_DECODE)
        try:
            image = cv2.imdecode(np.frombuffer(frame.jpeg, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error as exc:
            raise SyncNetError("Invalid JPEG frame", ErrorCode.E_DECODE) from exc
        if (
            image is None
            or image.dtype != np.uint8
            or image.ndim != 3
            or image.shape[2] != 3
            or not 0 < image.shape[0] <= 480
            or not 0 < image.shape[1] <= 640
        ):
            raise SyncNetError("Invalid JPEG frame", ErrorCode.E_DECODE)
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
        aligned = frontend.align_frame(rgb, landmarks, frame_index=index)
        if (
            not isinstance(aligned, np.ndarray)
            or aligned.dtype != np.uint8
            or aligned.shape != (SYNCNET_IMAGE_SIZE, SYNCNET_IMAGE_SIZE, 3)
        ):
            raise SyncNetError("Invalid aligned RGB square")
        if index in needed:
            retained[index] = aligned
    windows = [
        [retained[selected[position]] for position in range(start, start + SYNCNET_FRAMES)]
        for start in requested
    ]
    return FrontendProbeResult(
        windows,
        {
            "decoded_frames": len(recording.frames),
            "aligned_frames": len(recording.frames),
            "selected_frames": len(retained),
            "windows": len(windows),
        },
    )
