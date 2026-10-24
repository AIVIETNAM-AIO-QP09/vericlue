"""Shared face/iris observations for LIVE-02 and later FLOW-04.

API: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python
Landmark topology: google-ai-edge/mediapipe v0.10.21,
mediapipe/python/solutions/face_mesh_connections.py (indices only; no copied implementation).
The model's estimated transform is not measured physical depth or identity evidence.
"""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, TypeVar

import numpy as np
import yaml

from vericlue_ml.common.result import ErrorCode, Status

MAX_VIDEO_FRAMES = 1800
MAX_VIDEO_MS = 30_000
MAX_FRAME_PIXELS = 1920 * 1080
SAMPLE_INTERVAL_MS = 100
MAX_EXTRACT_SECONDS = 15
MIN_EYE_WIDTH_PX = 12
MIN_EYE_OPEN_RATIO = 0.10  # Provisional quality constants, not calibrated security thresholds.
Measurement = TypeVar("Measurement")


class LandmarkError(Exception):
    def __init__(self, code: ErrorCode, status: Status = Status.ERROR) -> None:
        super().__init__(str(code))
        self.code = code
        self.status = status


@dataclass(frozen=True)
class FaceObservation:
    at_ms: float
    face_count: int
    gaze_x: float | None = None
    gaze_y: float | None = None
    yaw_deg: float | None = None
    pitch_deg: float | None = None
    roll_deg: float | None = None


def pose_angles(matrix: np.ndarray) -> tuple[float, float, float] | None:
    """Read approximate yaw/pitch/roll from the model transform, stripping uniform scale."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        return None
    raw = matrix[:3, :3]
    u, scales, vt = np.linalg.svd(raw)
    if scales.min() < 1e-6 or scales.max() / scales.min() > 1.05:
        return None
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        return None
    yaw = math.atan2(rotation[0, 2], rotation[2, 2])
    pitch = math.atan2(-rotation[1, 2], math.hypot(rotation[0, 2], rotation[2, 2]))
    roll = math.atan2(rotation[1, 0], rotation[1, 1])
    return tuple(math.degrees(angle) for angle in (yaw, pitch, roll))


def eye_position(points: np.ndarray, width: int, height: int) -> tuple[float, float] | None:
    """Eye-relative iris motion proxy for unmirrored front-camera video, not screen gaze."""
    points = np.asarray(points, dtype=float)
    if points.shape != (478, 3) or not np.isfinite(points).all():
        return None
    xy = points[:, :2] * [width, height]
    estimates = []
    for corners, lids, ring in (
        ((33, 133), (159, 145), (469, 470, 471, 472)),
        ((362, 263), (386, 374), (474, 475, 476, 477)),
    ):
        left, right = sorted((xy[corners[0]], xy[corners[1]]), key=lambda p: p[0])
        axis = right - left
        eye_width = float(np.linalg.norm(axis))
        if eye_width < MIN_EYE_WIDTH_PX:
            return None
        axis /= eye_width
        vertical = np.array([-axis[1], axis[0]])
        opening = abs(float((xy[lids[1]] - xy[lids[0]]) @ vertical)) / eye_width
        if opening < MIN_EYE_OPEN_RATIO:
            return None
        iris = xy[list(ring)].mean(axis=0)
        horizontal = float((iris - left) @ axis) / eye_width
        center_y = (xy[lids[0]] + xy[lids[1]]) / 2
        y = float((iris - center_y) @ vertical) / eye_width
        if not 0 <= horizontal <= 1 or abs(y) > 0.5:
            return None
        estimates.append((1 - horizontal, y))
    return tuple(float(v) for v in np.mean(estimates, axis=0))


def observation_from_result(result: Any, at_ms: float, width: int, height: int) -> FaceObservation:
    """Keep absent/multiple faces and unusable eye geometry explicit."""
    count = len(result.face_landmarks)
    if count != 1:
        return FaceObservation(at_ms, count)
    points = np.asarray([(p.x, p.y, p.z) for p in result.face_landmarks[0]])
    matrices = result.facial_transformation_matrixes
    pose = pose_angles(matrices[0]) if len(matrices) == 1 else None
    eyes = eye_position(points, width, height)
    return FaceObservation(
        at_ms,
        count,
        *(eyes if eyes is not None else (None, None)),
        *(pose if pose is not None else (None, None, None)),
    )


class FaceObservationReader:
    """One CPU IMAGE-mode task per reader; no tracking state crosses session boundaries."""

    def __init__(
        self, *, model_path: Path | None = None, expected_sha256: str | None = None
    ) -> None:
        self.model_path = model_path
        self.expected_sha256 = expected_sha256
        self._task = None
        self._mp = None
        self._load_failed = False
        self._lock = RLock()

    def preload(self, *, models_dir: Path | None = None) -> None:
        """Load and hash-check an offline bundle once; a failure stays unavailable."""
        with self._lock:
            if self._task is not None:
                return
            if self._load_failed:
                raise LandmarkError(ErrorCode.E_INTERNAL)
            try:
                if self.model_path is None:
                    config_path = Path(
                        os.environ.get(
                            "ML_MODELS_CONFIG",
                            Path(__file__).resolve().parents[3] / "configs/models.yaml",
                        )
                    )
                    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["gaze"]
                    root = models_dir or Path(os.environ.get("MODELS_DIR", "models"))
                    relative = Path(config["model_subdir"]) / config["model_file"]
                    self.model_path = (root / relative).resolve()
                    if not self.model_path.is_relative_to(root.resolve()):
                        raise ValueError("Model path is outside MODELS_DIR")
                    self.expected_sha256 = config["sha256"]
                with self.model_path.open("rb") as handle:
                    checksum = hashlib.file_digest(handle, "sha256").hexdigest()
                if not self.expected_sha256 or checksum != self.expected_sha256:
                    raise LandmarkError(ErrorCode.E_INTEGRITY)
                import mediapipe as mp

                self._mp = mp
                options = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(
                        model_asset_path=str(self.model_path),
                        delegate=mp.tasks.BaseOptions.Delegate.CPU,
                    ),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=2,
                    output_facial_transformation_matrixes=True,
                )
                self._task = mp.tasks.vision.FaceLandmarker.create_from_options(options)
            except Exception:
                self._load_failed = True
                raise

    def extract(self, video: Path, *, start_ms: float, end_ms: float) -> list[FaceObservation]:
        """Sample by decoder timestamps; never manufacture timing from nominal FPS."""
        return self.extract_measurements(
            video,
            start_ms=start_ms,
            end_ms=end_ms,
            observer=lambda frame, time: self.observe(frame, at_ms=time),
        )

    def extract_measurements(
        self,
        video: Path,
        *,
        start_ms: float,
        end_ms: float,
        observer: Callable[[np.ndarray, float], Measurement],
    ) -> list[Measurement]:
        """Share bounded decoding with server-side measurements such as color ROIs."""
        if not 0 <= start_ms < end_ms <= MAX_VIDEO_MS:
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        if not video.is_file():
            raise LandmarkError(ErrorCode.E_DECODE)
        with video.open("rb") as handle:
            header = handle.read(12)
        if not (
            header.startswith(b"\x1aE\xdf\xa3")
            or header[4:8] == b"ftyp"
            or (header.startswith(b"RIFF") and header[8:12] == b"AVI ")
        ):
            raise LandmarkError(ErrorCode.E_DECODE)
        with self._lock:
            self.preload()
            import cv2

            capture = cv2.VideoCapture(str(video))
            started = perf_counter()
            previous = -1.0
            next_sample = start_ms
            observations = []
            try:
                if not capture.isOpened():
                    raise LandmarkError(ErrorCode.E_DECODE)
                for _ in range(MAX_VIDEO_FRAMES):
                    ok, frame = capture.read()
                    if not ok:
                        break
                    height, width = frame.shape[:2]
                    if height * width > MAX_FRAME_PIXELS:
                        raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
                    at_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                    if not math.isfinite(at_ms) or at_ms < 0 or at_ms <= previous:
                        raise LandmarkError(ErrorCode.E_DECODE)
                    if previous < 0 and at_ms > SAMPLE_INTERVAL_MS * 2:
                        raise LandmarkError(ErrorCode.E_INTEGRITY)
                    previous = at_ms
                    if at_ms > end_ms:
                        break
                    if perf_counter() - started > MAX_EXTRACT_SECONDS:
                        raise LandmarkError(ErrorCode.E_TIMEOUT)
                    if at_ms < next_sample:
                        continue
                    observations.append(observer(frame, at_ms))
                    next_sample = at_ms + SAMPLE_INTERVAL_MS - 1
                else:
                    raise LandmarkError(ErrorCode.E_TIMEOUT)
            finally:
                capture.release()
            return observations

    def observe(self, frame: np.ndarray, *, at_ms: float) -> FaceObservation:
        """Recheck the exact server-selected BGR frame with the same stateless task."""
        return self.measure(
            frame,
            at_ms=at_ms,
            transform=lambda result, rgb: observation_from_result(
                result, at_ms, rgb.shape[1], rgb.shape[0]
            ),
        )

    def measure(
        self,
        frame: np.ndarray,
        *,
        at_ms: float,
        transform: Callable[[Any, np.ndarray], Measurement],
    ) -> Measurement:
        """Run one validated landmark inference and transform it while holding the lock."""
        if (
            not isinstance(frame, np.ndarray)
            or frame.ndim != 3
            or frame.shape[2] != 3
            or frame.dtype != np.uint8
            or min(frame.shape[:2]) <= 0
            or frame.shape[0] * frame.shape[1] > MAX_FRAME_PIXELS
            or not math.isfinite(at_ms)
            or not 0 <= at_ms <= MAX_VIDEO_MS
        ):
            raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
        with self._lock:
            self.preload()
            import cv2

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._task.detect(
                self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            )
            return transform(result, rgb)

    def close(self) -> None:
        """Release the native task under the same lock as inference."""
        with self._lock:
            if self._task is not None:
                self._task.close()
                self._task = None
