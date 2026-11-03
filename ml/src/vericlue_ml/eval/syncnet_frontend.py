"""Ứng viên frontend SyncNet độc lập, chỉ dùng đánh giá ngoại tuyến.

Written from the independent mathematical specification dated 2026-11-03;
no StyleSync implementation was read, copied or translated. Public similarity
math: Matthew Earl, faceswap.py, revision
00cd82651d7640159739066d855162333e104d98 (MIT), lines 119 onward:
https://github.com/matthewearl/faceswap/blob/00cd82651d7640159739066d855162333e104d98/faceswap.py
Landmark groups, two rounding stages, chronological processing and Lanczos
resize are recorded caller facts from Apache LatentSync revision
a229c3948406bc2cf6eaf4873e662e70c6a04746, utils/image_processor.py and
utils/face_detector.py. Target coordinates, k=2.8, bias recurrence and dtype
settings are numeric observations supplied by that independent specification,
not copied implementation. They are not tuned on any evaluation media.

This candidate changes preprocessing identity and has no calibration or runtime
readiness claim. NumPy float32 geometry is not proven bit-equivalent to Torch
SVD; float32 warping is not evidence of upstream GPU float16 parity.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float32]
WarpDtype = Literal["float16", "float32"]
FRONTEND_VERSION = "syncnet-spatial-independent-v1-r256-numpy-float32"
# Engineering allowance for the FP32 bilinear sum and 127 * (1 - mask) fill:
# gamma_32 times the absolute byte/fill term budget, less than 0.001 byte.
# This conservative final-blend budget is NOT a universal Kornia error bound
# or an FP16/parity claim. It only permits excursions with identical uint8 cast.
_FP32_UNIT_ROUNDOFF = float(np.finfo(np.float32).eps) / 2
_BYTE_ROUNDOFF_BUDGET = (32 * _FP32_UNIT_ROUNDOFF / (1 - 32 * _FP32_UNIT_ROUNDOFF)) * (
    255 + 2 * 127
)


class SyncNetFrontendError(ValueError):
    """The offline candidate cannot produce a valid spatial input."""


@dataclass(frozen=True)
class SimilarityFit:
    """Forward pixel matrix and the dimensionless third-point bias."""

    matrix: FloatArray
    bias: FloatArray


@dataclass(frozen=True)
class FrameGeometry:
    """One frame's forward map with explicitly recorded smoothing state."""

    matrix: FloatArray
    bias: FloatArray
    smoothed_bias: FloatArray
    source_points: FloatArray
    frame_index: int


def _finite_array(values: np.ndarray, shape: tuple[int, ...], label: str) -> FloatArray:
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError, FloatingPointError) as exc:
        raise SyncNetFrontendError(f"{label} must be finite float32 coordinates") from exc
    if result.shape != shape or not np.isfinite(result).all():
        raise SyncNetFrontendError(f"{label} must have finite shape {shape}")
    return result


def three_points_from_landmarks(landmarks: np.ndarray) -> FloatArray:
    """Round all 106 original-image points, then round three group means."""
    rounded = np.rint(_finite_array(landmarks, (106, 2), "Landmarks"))
    groups = ([43, 48, 49, 51, 50], [101, 102, 103, 104, 105], [74, 77, 83, 86])
    return np.stack([np.rint(rounded[indices].mean(axis=0)) for indices in groups])


def _center_and_normalize(points: FloatArray) -> tuple[FloatArray, np.float32, FloatArray]:
    center = points.mean(axis=0)
    centered = points - center
    spread = centered.std(ddof=1)
    if not np.isfinite(spread) or spread <= 0:
        raise SyncNetFrontendError("Degenerate landmark spread")
    normalized = centered / spread
    singular = np.linalg.svd(normalized, compute_uv=False)
    if singular[1] <= np.finfo(np.float32).eps * max(normalized.shape) * singular[0]:
        raise SyncNetFrontendError("Degenerate landmark triangle")
    return center, spread, normalized


def fit_similarity(source: np.ndarray, target: np.ndarray) -> SimilarityFit:
    """Fit a forward proper rotation with sample-std scale, entirely float32."""
    source_points = _finite_array(source, (3, 2), "Source points")
    target_points = _finite_array(target, (3, 2), "Target points")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            source_center, source_std, source_unit = _center_and_normalize(source_points)
            target_center, target_std, target_unit = _center_and_normalize(target_points)
            left, _, right_t = np.linalg.svd(source_unit.T @ target_unit)
            right = right_t.T
            correction = np.eye(2, dtype=np.float32)
            correction[1, 1] = -1 if np.linalg.det(right @ left.T) < 0 else 1
            linear = (target_std / source_std) * (right @ correction @ left.T)
            translation = target_center - linear @ source_center
            matrix = np.column_stack((linear, translation))
            bias = target_unit[2] - source_unit[2]
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise SyncNetFrontendError("Unable to fit finite landmark geometry") from exc
    if not np.isfinite(matrix).all() or not np.isfinite(bias).all():
        raise SyncNetFrontendError("Nonfinite similarity result")
    return SimilarityFit(matrix=matrix, bias=bias)


class SyncNetFrontendCandidate:
    """Process every decoded frame from zero; reset before each new video.

    Never restart this object at a selected SyncNet window. Every intervening
    decoded frame must contribute to bias history, including unused windows.
    Missing/invalid geometry fails explicitly instead of fabricating a crop.
    The explicit CPU float32 default is a diagnostic variant of the recorded
    float16 upstream setting, not a silent dtype fallback.
    """

    intermediate_size_wh = (210, 280)

    def __init__(self, *, warp_dtype: WarpDtype = "float32", device: str = "cpu") -> None:
        if warp_dtype not in ("float16", "float32"):
            raise SyncNetFrontendError("Warp dtype must be explicit float16 or float32")
        self.warp_dtype = warp_dtype
        self.device = device
        self._previous_bias: FloatArray | None = None
        self._next_frame_index = 0

    @property
    def version(self) -> str:
        """Distinct preprocessing identity, never a production model version."""
        return f"{FRONTEND_VERSION}+kornia-{self.warp_dtype}"

    @property
    def target_points(self) -> FloatArray:
        """Observed target at r=256, returned without shared mutable storage."""
        return np.float32(2.8) * np.array([[17, 20], [58, 20], [37.5, 40]], dtype=np.float32)

    def reset(self) -> None:
        """Start a new video with no inherited bias and frame index zero."""
        self._previous_bias = None
        self._next_frame_index = 0

    def _propose_geometry(self, landmarks: np.ndarray, frame_index: int) -> FrameGeometry:
        if (
            isinstance(frame_index, bool)
            or not isinstance(frame_index, Integral)
            or frame_index != self._next_frame_index
        ):
            raise SyncNetFrontendError(
                "Frames must be consecutive from zero; reset for a new video"
            )
        points = three_points_from_landmarks(landmarks)
        fit = fit_similarity(points, self.target_points)
        history = (
            fit.bias.copy()
            if self._previous_bias is None
            else np.float32(0.2) * self._previous_bias + np.float32(0.8) * fit.bias
        )
        matrix = fit.matrix.copy()
        matrix[:, 2] += history
        if not np.isfinite(matrix).all():
            raise SyncNetFrontendError("Nonfinite smoothed transform")
        return FrameGeometry(matrix, fit.bias, history, points, int(frame_index))

    def _commit_geometry(self, geometry: FrameGeometry) -> None:
        self._previous_bias = geometry.smoothed_bias.copy()
        self._next_frame_index += 1

    def geometry_for_frame(self, landmarks: np.ndarray, *, frame_index: int) -> FrameGeometry:
        """Advance chronological bias history without requiring image libraries."""
        geometry = self._propose_geometry(landmarks, frame_index)
        self._commit_geometry(geometry)
        return geometry

    def align_frame(
        self, frame_rgb: np.ndarray, landmarks: np.ndarray, *, frame_index: int
    ) -> NDArray[np.uint8]:
        """Align one RGB byte frame, committing history only after successful resize.

        Use this OR geometry_for_frame for each frame, never both on one index.
        Face availability/multiface checks belong to the caller and must run
        before this method; this class neither selects nor detects a face.
        """
        geometry = self._propose_geometry(landmarks, frame_index)
        aligned = warp_rgb_kornia(
            frame_rgb,
            geometry.matrix,
            size_wh=self.intermediate_size_wh,
            warp_dtype=self.warp_dtype,
            device=self.device,
        )
        square = resize_aligned_to_square(aligned)
        self._commit_geometry(geometry)
        return square


def warp_rgb_kornia(
    frame_rgb: np.ndarray,
    matrix: np.ndarray,
    *,
    size_wh: tuple[int, int] = (210, 280),
    warp_dtype: WarpDtype = "float32",
    device: str = "cpu",
) -> np.ndarray:
    """Warp forward pixel coordinates using licensed Kornia, with no dtype fallback.

    Boundary contract: Kornia 0.8.0 geometry/transform/imgwarp.py (Apache-2.0),
    bilinear, align_corners=True, RGB fill=127 with fractional boundary support.
    Imports are lazy; optional dependencies are never downloaded here. A backend
    without the requested float16/float32 kernel raises an explicit error.
    """
    pixels = np.asarray(frame_rgb)
    if (
        pixels.dtype != np.uint8
        or pixels.ndim != 3
        or pixels.shape[2] != 3
        or min(pixels.shape[:2]) < 2
    ):
        raise SyncNetFrontendError("Warp input must be RGB uint8 with both sides at least two")
    forward = _finite_array(matrix, (2, 3), "Warp matrix")
    if len(size_wh) != 2 or any(
        isinstance(side, bool) or not isinstance(side, Integral) or side < 2 for side in size_wh
    ):
        raise SyncNetFrontendError("Warp output size must contain two integers of at least two")
    if warp_dtype not in ("float16", "float32"):
        raise SyncNetFrontendError("Warp dtype must be explicit float16 or float32")
    # Validate again after the requested storage conversion: float16 can lose a
    # small scale or overflow a translation that was valid in float32 geometry.
    try:
        with np.errstate(over="raise", invalid="raise"):
            stored = forward.astype(warp_dtype).astype(np.float32)
        if not np.isfinite(stored).all() or np.linalg.det(stored[:, :2]) == 0:
            raise SyncNetFrontendError("Warp matrix is degenerate at the requested precision")
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise SyncNetFrontendError("Warp matrix is invalid at the requested precision") from exc
    try:
        import torch
        from kornia.geometry.transform import warp_affine
    except ImportError as exc:
        raise SyncNetFrontendError("Optional Torch and Kornia are required for this warp") from exc
    dtype = torch.float16 if warp_dtype == "float16" else torch.float32
    try:
        with torch.inference_mode():
            image = torch.from_numpy(np.ascontiguousarray(pixels)).permute(2, 0, 1)[None]
            image = image.to(device=device, dtype=dtype)
            affine = torch.from_numpy(np.ascontiguousarray(forward))[None].to(
                device=device, dtype=dtype
            )
            result = warp_affine(
                image,
                affine,
                dsize=(int(size_wh[1]), int(size_wh[0])),
                mode="bilinear",
                padding_mode="fill",
                align_corners=True,
                fill_value=torch.full((3,), 127, device=device, dtype=dtype),
            )
            output = result[0].permute(1, 2, 0).contiguous().cpu().numpy()
    except (RuntimeError, NotImplementedError, TypeError, ValueError) as exc:
        raise SyncNetFrontendError(
            f"Kornia {warp_dtype} warp failed on {device}; no dtype fallback"
        ) from exc
    if not np.isfinite(output).all():
        raise SyncNetFrontendError("Kornia produced nonfinite pixels")
    return output


def resize_aligned_to_square(aligned_rgb: np.ndarray) -> NDArray[np.uint8]:
    """Allow tiny blend roundoff, then truncate bytes before Lanczos4 at 256²."""
    pixels = np.asarray(aligned_rgb)
    if (
        pixels.ndim != 3
        or pixels.shape[2] != 3
        or min(pixels.shape[:2]) < 1
        or not np.issubdtype(pixels.dtype, np.number)
        or not np.isfinite(pixels).all()
    ):
        raise SyncNetFrontendError("Aligned RGB must contain finite pixels in [0, 255]")
    minimum, maximum = float(pixels.min()), float(pixels.max())
    if minimum < -_BYTE_ROUNDOFF_BUDGET or maximum > 255 + _BYTE_ROUNDOFF_BUDGET:
        raise SyncNetFrontendError("Aligned RGB exceeds the byte-range roundoff budget")
    if minimum < 0 or maximum > 255:
        # These excursions are much smaller than one byte: clipping has exactly
        # the same uint8 result as direct truncation toward zero at either edge.
        pixels = np.clip(pixels, 0, 255)
    try:
        import cv2
    except ImportError as exc:
        raise SyncNetFrontendError("OpenCV is required for Lanczos4 resizing") from exc
    return cv2.resize(pixels.astype(np.uint8), (256, 256), interpolation=cv2.INTER_LANCZOS4)


def pack_syncnet_frames(frames_rgb: np.ndarray) -> FloatArray:
    """Pack sixteen aligned 256² RGB byte frames to [1,48,128,256], [-1,1].

    These inputs are already 256² after Lanczos; the downstream byte resize
    therefore has no size change. Channels are ordered frame0 RGB, frame1 RGB,
    etc. Only the lower half reaches the visual encoder. No Torch is needed.
    """
    frames = np.asarray(frames_rgb)
    if frames.dtype != np.uint8 or frames.shape != (16, 256, 256, 3):
        raise SyncNetFrontendError("Expected exactly sixteen 256x256 RGB uint8 frames")
    normalized = (
        frames[:, 128:, :, :].astype(np.float32) / np.float32(255) - np.float32(0.5)
    ) / np.float32(0.5)
    return np.ascontiguousarray(normalized.transpose(0, 3, 1, 2).reshape(1, 48, 128, 256))
