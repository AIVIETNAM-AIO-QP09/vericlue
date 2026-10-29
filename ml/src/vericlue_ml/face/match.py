"""FLOW-05: SCRFD + LVFace-B embeddings, with optional server-owned calibrated threshold.

LVFace RGB/112/[-1,1] preprocessing: bytedance/LVFace commit
80bd20c8bb78e56eb708941180d800a27c396a6b, inference_onnx.py::_preprocess_image.
ArcFace five-point target: deepinsight/insightface, utils/face_align.py.
Similarity transform below is our least-squares implementation; no vendor code is copied.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from itertools import combinations
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Literal, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.device import check_onnx_session, onnx_providers
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.pad import (
    FaceFinder,
    PadError,
    ScrfdFaceFinder,
    _decode,
    _models_root,
    _verified_weights,
    shared_scrfd_session,
)

MODEL_FILE = "LVFace-B_Glint360K.onnx"
LVFACE_REVISION = "b12702ab1f5c721748e054a66dc90e1edd1f0724"
SCRFD_REVISION = "bfcc7d48ea8412d55de406cecf96b65b3ca720b2"
ALIGNMENT_ID = "arcface112-rgb-minus1to1-v1"
MATCH_VERSION = (
    "lvface-b@b12702ab1f5c7217+scrfd10g@bfcc7d48+" + ALIGNMENT_ID + "+front-reference-v2"
)
MIN_FACE_SIDE = 40
MAX_ALIGNMENT_ERROR_PX = 10
ARCFACE_TARGET = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float64,
)


class MatchError(PadError):
    def __init__(self, code: ErrorCode, status: Status = Status.ERROR) -> None:
        super().__init__(str(code), code)
        self.status = status


def similarity_transform(points: np.ndarray) -> np.ndarray:
    """Fit orientation-preserving 2D scale/rotation/translation to the five landmarks."""
    points = np.asarray(points, dtype=float)
    if points.shape != (5, 2) or not np.isfinite(points).all():
        raise MatchError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
    design = np.zeros((10, 4))
    x, y = points.T
    design[0::2] = np.column_stack([x, -y, np.ones(5), np.zeros(5)])
    design[1::2] = np.column_stack([y, x, np.zeros(5), np.ones(5)])
    params, _, rank, _ = np.linalg.lstsq(design, ARCFACE_TARGET.reshape(-1), rcond=None)
    a, b, tx, ty = params
    error = np.sqrt(np.mean((design @ params - ARCFACE_TARGET.reshape(-1)) ** 2))
    if rank != 4 or np.hypot(a, b) < 1e-6 or error > MAX_ALIGNMENT_ERROR_PX:
        raise MatchError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
    return np.array([[a, -b, tx], [b, a, ty]], dtype=np.float32)


def align_face112(image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    """Produce a 112x112 BGR crop without GenD's extra context margin."""
    import cv2

    return cv2.warpAffine(
        image, similarity_transform(landmarks), (112, 112), flags=cv2.INTER_LINEAR, borderValue=0
    )


def match_tensor(aligned_bgr: np.ndarray) -> np.ndarray:
    """LVFace's published RGB CHW float32 normalization after five-point alignment."""
    if aligned_bgr.shape != (112, 112, 3) or aligned_bgr.dtype != np.uint8:
        raise MatchError(ErrorCode.E_DECODE)
    rgb_chw = aligned_bgr[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)
    return np.ascontiguousarray((rgb_chw / 127.5 - 1.0)[None])


def normalized(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    length = float(np.linalg.norm(vector))
    if (
        vector.size != 512
        or not np.isfinite(vector).all()
        or not np.isfinite(length)
        or length < 1e-8
    ):
        raise MatchError(ErrorCode.E_INTERNAL)
    return vector / length


class Embedder(Protocol):
    def embed(self, tensor: np.ndarray) -> np.ndarray: ...


class LVFaceEmbedder:
    """Original ONNX weights, one offline session per backend; no conversion or fallback model."""

    def __init__(self) -> None:
        self.session = None
        self._failed = False
        self._lock = RLock()

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        with self._lock:
            if self.session is not None:
                return
            if self._failed:
                raise MatchError(ErrorCode.E_INTERNAL)
            try:
                import onnxruntime as ort

                path, revision = _verified_weights(_models_root(models_dir), "lvface-b", MODEL_FILE)
                if revision != LVFACE_REVISION:
                    raise MatchError(ErrorCode.E_INTEGRITY)
                options = ort.SessionOptions()
                options.intra_op_num_threads = 4
                options.inter_op_num_threads = 1
                options.log_severity_level = 3
                self.session = ort.InferenceSession(
                    str(path),
                    sess_options=options,
                    providers=onnx_providers(device, component="lvface-b"),
                )
                check_onnx_session(self.session, device, component="lvface-b")
                inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
                if (
                    len(inputs) != 1
                    or len(outputs) != 1
                    or inputs[0].type != "tensor(float)"
                    or inputs[0].shape[-3:] != [3, 112, 112]
                ):
                    self.session = None
                    raise MatchError(ErrorCode.E_INTEGRITY)
                self.input_name, self.output_name = inputs[0].name, outputs[0].name
            except Exception:
                self.session = None
                self._failed = True
                raise

    def embed(self, tensor: np.ndarray) -> np.ndarray:
        with self._lock:
            self.preload()
            result = self.session.run([self.output_name], {self.input_name: tensor})[0]
            if result.shape != (1, 512):
                raise MatchError(ErrorCode.E_INTEGRITY)
            return normalized(result)


class MatchThreshold(BaseModel):
    """Internal artifact provenance; no client-supplied threshold or implicit default."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, strict=True)
    model_version: str
    preprocessing: Literal["arcface112-rgb-minus1to1-v1"]
    threshold: float = Field(ge=-1, le=1)
    split: Literal["calib_ltt"]
    dataset: str = Field(min_length=1)
    pairs: int = Field(gt=0)
    subjects: int = Field(ge=2)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    predictions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FaceMatchDetector:
    """Compare reference to front; report cross-view consistency separately as raw evidence."""

    name = Module.FACE_MATCH.value
    version = MATCH_VERSION

    def __init__(
        self,
        *,
        finder: FaceFinder | None = None,
        embedder: Embedder | None = None,
        calibration_path: Path | None = None,
        consistency_path: Path | None = None,
    ) -> None:
        self.finder = finder
        self.embedder = embedder if embedder is not None else LVFaceEmbedder()
        self.calibration_path = calibration_path
        self.consistency_path = consistency_path
        self._consistency_threshold: MatchThreshold | None = None
        self._threshold: MatchThreshold | None = None
        self._loaded = self._failed = False
        self._lock = RLock()

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        with self._lock:
            if self._loaded:
                return
            if self._failed:
                raise MatchError(ErrorCode.E_INTERNAL)
            try:
                if self.finder is None:
                    session, revision = shared_scrfd_session(_models_root(models_dir), device)
                    if revision != SCRFD_REVISION:
                        raise MatchError(ErrorCode.E_INTEGRITY)
                    self.finder = ScrfdFaceFinder(session, scale=128.0, swap_rb=True)
                if isinstance(self.embedder, LVFaceEmbedder):
                    self.embedder.preload(models_dir=models_dir, device=device)
                artifact = self.calibration_path or os.environ.get("FACE_MATCH_CALIBRATION")
                if artifact is not None:
                    self._threshold = MatchThreshold.model_validate_json(
                        Path(artifact).read_text(encoding="utf-8")
                    )
                    if self._threshold.model_version != self.version:
                        raise MatchError(ErrorCode.E_INTEGRITY)
                if self.consistency_path is not None:
                    self._consistency_threshold = MatchThreshold.model_validate_json(
                        self.consistency_path.read_text(encoding="utf-8")
                    )
                    if (
                        self._consistency_threshold.model_version
                        != self.version + "+view-consistency-v1"
                    ):
                        raise MatchError(ErrorCode.E_INTEGRITY)
                self._loaded = True
            except Exception:
                self._failed = True
                raise

    def _embedding(self, source: Path | np.ndarray) -> tuple[np.ndarray, str]:
        image = _decode(source) if isinstance(source, Path) else source
        if (
            not isinstance(image, np.ndarray)
            or image.ndim != 3
            or image.shape[2] != 3
            or image.dtype != np.uint8
            or min(image.shape[:2]) <= 0
        ):
            raise MatchError(ErrorCode.E_DECODE, Status.DEGRADED)
        faces = self.finder.find(image)
        if not faces:
            raise MatchError(ErrorCode.E_NO_FACE, Status.NOT_APPLICABLE)
        if len(faces) != 1:
            raise MatchError(ErrorCode.E_MULTI_FACE, Status.NOT_APPLICABLE)
        face = faces[0]
        if face.landmarks is None or min(face.x2 - face.x1, face.y2 - face.y1) < MIN_FACE_SIDE:
            raise MatchError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
        crop = align_face112(image, np.asarray(face.landmarks))
        vector = normalized(self.embedder.embed(match_tensor(crop)))
        return vector, hashlib.sha256(image.tobytes()).hexdigest()

    def predict(self, inp: DetectorInput) -> ModuleResult:
        return self._predict(inp, inp.image_roles, inp.images)

    def embed_frames(self, frames: Mapping[str, np.ndarray]) -> dict[str, tuple[np.ndarray, str]]:
        """Internal trusted pixels → RAM vectors/hashes; never serialize to detector responses."""
        with self._lock:
            self.preload()
            return {name: self._embedding(frame) for name, frame in frames.items()}

    def predict_frames(
        self,
        inp: DetectorInput,
        frames: Mapping[str, np.ndarray],
        *,
        reference_frame: np.ndarray | None = None,
    ) -> ModuleResult:
        """Internal ML call with decoded server-selected pixels; no frames are written to disk.

        Ignore inp.images/image_roles: frame roles here are owned by the video pipeline.
        This is not an additional JSON/HTTP input field.
        reference_frame is a trusted internal RAM alternative, used by the local webcam lab.
        It does not create a client-controlled reference resolver or change preprocessing.
        """
        return self._predict(
            inp, list(frames), list(frames.values()), reference_frame=reference_frame
        )

    def _predict(
        self,
        inp: DetectorInput,
        roles: list[str],
        sources: list[Path | np.ndarray],
        *,
        reference_frame: np.ndarray | None = None,
    ) -> ModuleResult:
        started = perf_counter()
        try:
            reference_source = (
                reference_frame if reference_frame is not None else inp.reference_image
            )
            if reference_source is None:
                raise MatchError(ErrorCode.E_DECODE, Status.DEGRADED)
            if (
                len(sources) not in (1, 3)
                or len(roles) != len(sources)
                or set(roles) != ({"front"} if len(roles) == 1 else {"front", "left", "right"})
            ):
                raise MatchError(ErrorCode.E_CHALLENGE_MISMATCH, Status.DEGRADED)
            with self._lock:
                self.preload()
                reference, reference_hash = self._embedding(reference_source)
                vectors, hashes = {}, []
                for role, source in zip(roles, sources, strict=True):
                    vector, checksum = self._embedding(source)
                    if checksum == reference_hash:
                        raise MatchError(ErrorCode.E_INTEGRITY, Status.DEGRADED)
                    vectors[role] = vector
                    hashes.append(checksum)
                if len(set(hashes)) != len(hashes):
                    raise MatchError(ErrorCode.E_INTEGRITY, Status.DEGRADED)
                frontal_cosine = float(np.clip(reference @ vectors["front"], -1, 1))
                similarities = {"reference_front": frontal_cosine}
                view_similarities = {
                    a + "_" + b: float(np.clip(vectors[a] @ vectors[b], -1, 1))
                    for a, b in combinations(sorted(vectors), 2)
                }
                available = self._threshold is not None
                passed = available and frontal_cosine >= self._threshold.threshold
                return ModuleResult(
                    module=Module.FACE_MATCH,
                    model_version=self.version,
                    status=Status.OK if available else Status.DEGRADED,
                    gate=(Gate.PASS if passed else Gate.FAIL) if available else Gate.UNCLEAR,
                    score=1 - frontal_cosine,
                    quality={
                        "threshold_available": available,
                        "views": len(roles),
                        "comparisons": len(similarities),
                        "threshold_cosine": self._threshold.threshold if available else None,
                        "consistency_comparisons": len(view_similarities),
                        "consistency_verified": bool(
                            len(view_similarities) == 3
                            and self._consistency_threshold is not None
                            and min(view_similarities.values())
                            >= self._consistency_threshold.threshold
                        ),
                        "consistency_threshold_available": self._consistency_threshold is not None,
                        "consistency_threshold_cosine": self._consistency_threshold.threshold
                        if self._consistency_threshold is not None
                        else None,
                    },
                    evidence=[
                        Evidence(
                            type="text",
                            name="match_scope",
                            value="reference_to_front_only_not_liveness",
                        ),
                        Evidence(type="scalar", name="cosine_similarities", value=similarities),
                        Evidence(
                            type="scalar", name="view_cosine_similarities", value=view_similarities
                        ),
                    ],
                    latency_ms=(perf_counter() - started) * 1000,
                )
        except Exception as exc:
            return ModuleResult(
                module=Module.FACE_MATCH,
                model_version=self.version,
                status=exc.status if isinstance(exc, MatchError) else Status.ERROR,
                error_code=exc.code if isinstance(exc, PadError) else ErrorCode.E_INTERNAL,
                gate=Gate.UNCLEAR,
                latency_ms=(perf_counter() - started) * 1000,
            )
