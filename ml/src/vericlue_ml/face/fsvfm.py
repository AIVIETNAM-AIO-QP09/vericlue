"""FS-VFM-L FAS diagnostic; original FP32 weights, no remote code or calibrated gate.

Pinned architecture/evaluation: FSFM-CVPR25@b84aafa2507c30bb4986564de8262969647e450c,
fsvfm/finetune/cross_domain_FAS/{fas,models_vit,utils/dataset,utils/evaluate}.py.
Upstream evaluates pre-cropped MTCNN faces. Our SCRFD five-point alignment is an
explicit deployment variant, versioned separately; upstream benchmark parity is
NOT established. Dataset RGB/BICUBIC/224 normalization and FAS head are retained.
Weights are research/noncommercial, not a commercial deployment endorsement.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.device import resolve_torch_device
from vericlue_ml.common.result import ErrorCode, Evidence, Module, ModuleResult, Status
from vericlue_ml.face.gend import _limit_cpu_threads
from vericlue_ml.face.match import similarity_transform
from vericlue_ml.face.pad import (
    FaceFinder,
    PadError,
    ScrfdFaceFinder,
    _decode,
    _models_root,
    _verified_weights,
    shared_scrfd_session,
)

MODEL_ID = "fs-vfm-vit-l-fas"
CHECKPOINT_FILE = "msu_vit_0_shot_checkpoint_run_0.pth.tar"
STATS_FILE = "pretrain_ds_mean_std.txt"
PREPROCESS_VERSION = "scrfd128-align224-rgb-v1"
MEAN = (0.5482207536697388, 0.42340534925460815, 0.3654651641845703)
STD = (0.2789176106452942, 0.2438540756702423, 0.23493893444538116)
ROLES = ("front", "left", "right")


class FasClassifier(Protocol):
    def p_fake(self, batch: np.ndarray) -> list[float]: ...


def face_tensor(aligned_bgr: np.ndarray) -> np.ndarray:
    """Dataset tensor transform; caller supplies a face crop, not a full camera image."""
    from PIL import Image

    rgb = Image.fromarray(aligned_bgr[:, :, ::-1]).resize((224, 224), Image.Resampling.BICUBIC)
    value = np.asarray(rgb, dtype=np.float32) / 255
    return np.ascontiguousarray(((value - MEAN) / STD).transpose(2, 0, 1), dtype=np.float32)


def aligned_face(frame: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    """Warp directly to 224px, avoiding an intermediate 112px downsample for PAD."""
    import cv2

    return cv2.warpAffine(
        frame,
        similarity_transform(landmarks) * 2,
        (224, 224),
        flags=cv2.INTER_LINEAR,
        borderValue=0,
    )


class TorchFasClassifier:
    def __init__(self, network, device: str) -> None:
        self.network, self.device = network, device
        self._lock = threading.Lock()

    def p_fake(self, batch: np.ndarray) -> list[float]:
        import torch

        # One view at a time bounds activation memory on the 6 GB demo GPU.
        with self._lock, torch.inference_mode():
            scores = []
            for frame in batch:
                logits = self.network(torch.from_numpy(frame[None]).to(self.device))
                scores.append(float(logits.softmax(dim=-1)[0, 0].cpu()))
            return scores


def load_classifier(root: Path, device: str | None = None) -> tuple[TorchFasClassifier, str]:
    """Only SHA-verified local bytes; minimal scoped NumPy scalar allowlist, never pickle fallback."""
    import torch

    try:
        from numpy._core.multiarray import scalar
    except ImportError:  # NumPy 1.26 still exposes this through numpy.core.
        from numpy.core.multiarray import scalar

    from vericlue_ml.face.fsvfm_network import FasNetwork, checkpoint_state

    path, revision = _verified_weights(root, MODEL_ID, CHECKPOINT_FILE)
    stats, _ = _verified_weights(root, MODEL_ID, STATS_FILE)
    normalization = json.loads(stats.read_text(encoding="utf-8").splitlines()[0])
    if not np.allclose(normalization["mean"], MEAN, atol=0, rtol=0) or not np.allclose(
        normalization["std"], STD, atol=0, rtol=0
    ):
        raise PadError("Unexpected FS-VFM normalization", ErrorCode.E_INTEGRITY)
    target = resolve_torch_device(device, component=MODEL_ID)
    _limit_cpu_threads(target)
    try:
        with torch.serialization.safe_globals(
            [(scalar, "numpy.core.multiarray.scalar"), np.dtype, np.dtypes.Float64DType]
        ):
            checkpoint = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        state = checkpoint_state(checkpoint["state_dict"])
        with torch.device("meta"):
            network = FasNetwork()
        network.load_state_dict(state, strict=True, assign=True)
        if not all(torch.isfinite(t).all().item() for t in network.state_dict().values()):
            raise ValueError("Nonfinite weights")
        if (network.classifier.weight.norm(dim=0) == 0).any().item():
            raise ValueError("Zero classifier norm")
    except Exception as exc:
        raise PadError("Invalid FS-VFM checkpoint", ErrorCode.E_INTEGRITY) from exc
    network.eval().to(target)
    return TorchFasClassifier(network, target), revision


class FsvfmPadDetector:
    """Opt-in PAD diagnostic, independent of the legacy MiniFASNet registry default."""

    name = Module.FACE_PAD.value

    def __init__(
        self,
        models_dir: Path | str | None = None,
        *,
        finder: FaceFinder | None = None,
        classifier: FasClassifier | None = None,
    ) -> None:
        self._models_dir = models_dir
        self._finder, self._classifier = finder, classifier
        self._loaded_root = None
        self._lock = threading.Lock()
        self.version = f"{MODEL_ID}+{PREPROCESS_VERSION}"

    @property
    def frames_version(self) -> str:
        return self.version + "+headturn-3views-max-v1"

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        with self._lock:
            root = _models_root(models_dir if models_dir is not None else self._models_dir)
            if self._finder is not None and self._classifier is not None:
                if (
                    models_dir is not None
                    and self._loaded_root is not None
                    and root.resolve() != self._loaded_root
                ):
                    raise PadError("FS-VFM already loaded with another model root")
                return
            session, det_revision = shared_scrfd_session(root, device)
            classifier, revision = load_classifier(root, device)
            self._finder = ScrfdFaceFinder(session, scale=128.0, swap_rb=True)
            self._classifier = classifier
            self._loaded_root = root.resolve()
            self.version = (
                f"{MODEL_ID}@{revision[:8]}+scrfd@{det_revision[:8]}+{PREPROCESS_VERSION}"
            )

    def predict(self, inp: DetectorInput) -> ModuleResult:
        """Single frontal image diagnostic; video requires explicit server-selected views."""
        try:
            if len(inp.images) != 1 or inp.video is not None:
                raise PadError("Expected one face image", ErrorCode.E_DECODE)
            return self._measure({"front": _decode(inp.images[0])}, three_views=False)
        except Exception as exc:
            return ModuleResult(
                module=Module.FACE_PAD,
                model_version=self.version,
                status=Status.ERROR,
                error_code=exc.code if isinstance(exc, PadError) else ErrorCode.E_INTERNAL,
                latency_ms=0,
            )

    def predict_frames(self, inp: DetectorInput, frames: Mapping[str, np.ndarray]) -> ModuleResult:
        """Score the exact RAM frames; do not open inp.video or client-supplied images."""
        return self._measure(frames, three_views=True)

    def predict_frame(self, inp: DetectorInput, frame: np.ndarray) -> ModuleResult:
        """Single RAM frame using the same transform/version as single-image predict()."""
        return self._measure({"front": frame}, three_views=False)

    def _measure(self, frames: Mapping[str, np.ndarray], *, three_views: bool) -> ModuleResult:
        started = time.perf_counter()

        def result(status, **fields):
            return ModuleResult(
                module=Module.FACE_PAD,
                model_version=self.frames_version if three_views else self.version,
                status=status,
                latency_ms=(time.perf_counter() - started) * 1000,
                **fields,
            )

        try:
            roles = ROLES if three_views else ("front",)
            if set(frames) != set(roles):
                return result(Status.DEGRADED, error_code=ErrorCode.E_CHALLENGE_MISMATCH)
            values = [frames[role] for role in roles]
            if any(
                not isinstance(f, np.ndarray)
                or f.ndim != 3
                or f.shape[2] != 3
                or f.dtype != np.uint8
                or min(f.shape[:2]) == 0
                or f.shape[0] * f.shape[1] > 1920 * 1080
                for f in values
            ):
                return result(Status.DEGRADED, error_code=ErrorCode.E_DECODE)
            if len({hashlib.sha256(f.tobytes()).digest() for f in values}) != len(values):
                return result(Status.DEGRADED, error_code=ErrorCode.E_INTEGRITY)
            self.preload()
            crops = []
            for frame in values:
                faces = self._finder.find(frame)
                if len(faces) != 1:
                    return result(
                        Status.NOT_APPLICABLE,
                        error_code=ErrorCode.E_NO_FACE if not faces else ErrorCode.E_MULTI_FACE,
                    )
                face = faces[0]
                if face.landmarks is None or min(face.x2 - face.x1, face.y2 - face.y1) < 40:
                    return result(Status.DEGRADED, error_code=ErrorCode.E_LOW_QUALITY)
                crops.append(face_tensor(aligned_face(frame, np.asarray(face.landmarks))))
            scores = self._classifier.p_fake(np.stack(crops))
            if len(scores) != len(roles) or not all(
                math.isfinite(p) and 0 <= p <= 1 for p in scores
            ):
                raise PadError("Invalid FS-VFM scores")
            return result(
                Status.OK,
                score=max(scores),
                quality={
                    "provisional": True,
                    "frames_used": len(scores),
                    "upstream_crop_parity": False,
                },
                evidence=[
                    Evidence(
                        type="timeseries",
                        name="view_scores",
                        value=dict(zip(roles, scores, strict=True)),
                    ),
                    Evidence(
                        type="text", name="score_scope", value="raw_uncalibrated_pad_not_depth"
                    ),
                ],
            )
        except PadError as exc:
            return result(
                Status.DEGRADED if exc.code == ErrorCode.E_LOW_QUALITY else Status.ERROR,
                error_code=exc.code,
            )
        except Exception:
            return result(Status.ERROR, error_code=ErrorCode.E_INTERNAL)
