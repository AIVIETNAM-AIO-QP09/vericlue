"""FACE-02 — phát hiện deepfake khuôn mặt bằng GenD (CLIP ViT-L/14 tinh chỉnh LayerNorm + đầu tuyến tính).

Luồng: video (hoặc ảnh) → lấy N khung đều nhau → SCRFD `det_10g` → mặt lớn nhất mỗi khung → căn chỉnh
5 điểm (tỷ lệ 1,3) → 224 px, mean/std của CLIP → GenD → softmax → `p_fake` mỗi khung. Điểm video:
`score = max(mean, top25_mean)` của `p_fake` (điểm thô; `prob_attack` để trống chờ hiệu chỉnh, như
`face/pad.py`). Không có mặt ở mọi khung → `not_applicable` (E_NO_FACE); quá ít khung có mặt →
`degraded` (không bao giờ được coi là đạt); thiếu trọng số, sai SHA-256 hay lỗi bất kỳ → `error`.

Mã KHÔNG gọi mạng: trọng số đọc từ `MODELS_DIR/<id trong models/manifest.yaml>/<file>` và kiểm SHA-256.
Backbone dựng từ `config.json` của `clip-vit-large-patch14` rồi nạp trọng số vision từ checkpoint GenD
(không dùng `GenD.from_pretrained` vì nó tải CLIP từ mạng và chạy mã từ xa).

Nguồn tiền xử lý (chép lại, giữ giấy phép — xem `third_party/README.md`):
- yermandy/GenD (MIT, Copyright (c) 2025 Andy), commit 387a42266dd385fbe8f7626c5d3aa03eea3bfaab:
  `detector.py::align_face` (mốc đích, `estimateAffinePartial2D` LMEDS, `target_size=None` rồi để
  CLIP resize về 224), `src/retinaface.py` (SCRFD: letterbox 640, `blobFromImage(1/128, mean 127.5,
  swapRB)`, NMS 0,4), `src/hf/modeling_gend.py` (`pooler_output` → L2-normalize → Linear(1024, 2)),
  `app/run.py` (BGR→RGB, softmax, nhãn 1 = giả). Mean/std và nội suy BICUBIC theo
  `preprocessor_config.json` của CLIP.
- `top25_mean` là quy ước riêng của VeriClue (ADR-0004), không có ở repo gốc.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.device import resolve_torch_device
from vericlue_ml.common.result import (
    ErrorCode,
    Evidence,
    EvidenceType,
    Module,
    ModuleResult,
    Status,
)
from vericlue_ml.face.frames import Frames, sample_images, sample_video
from vericlue_ml.face.pad import (
    FaceBox,
    FaceFinder,
    PadError,
    ScrfdFaceFinder,
    _models_root,
    _verified_weights,
    shared_scrfd_session,
)

GEND_MODEL_ID = "gend-clip-l14"
CLIP_MODEL_ID = "clip-vit-large-patch14"
GEND_WEIGHTS = "model.safetensors"
GEND_CONFIG = "config.json"
CLIP_CONFIG = "config.json"
CLIP_PREPROCESSOR = "preprocessor_config.json"

# Số khung lấy mẫu: giám định 32 theo task card FACE-02; eKYC 8 là lựa chọn của wrapper vì tốc độ
# (ngân sách detector 4 s), xem bàn giao FACE-02.
EKYC_FRAMES = 8
FORENSIC_FRAMES = 32
FORENSIC_MODE = "forensic"  # `DetectorInput.metadata["mode"]`; không có thì coi là eKYC

# Hậu tố của model_version: cách gộp điểm khung → video. Đổi cách gộp (mean/top25/max) thì ĐỔI hậu tố này,
# vì calibrator được khóa theo model_version. Số khung (8 hay 32) KHÔNG nằm trong version, mà ở evidence.
AGGREGATION_TAG = "agg-maxmeantop25-v1"
HEAD_VIEWS_TAG = "headturn-3views-v1"
MAX_VIEW_PIXELS = 1920 * 1080
MIN_VIEW_FACE_SIDE_PX = 40  # Provisional quality bound, not a calibrated security threshold.
# Số luồng CPU của torch khi GenD chạy CPU: đủ nhanh mà không chiếm hết lõi của face_pad/quality/voice.
# `torch.set_num_threads` là cài đặt toàn tiến trình (voice cũng đặt 4 qua `cpu_threads`).
GEND_CPU_THREADS = 4

ALIGN_SCALE = 1.3  # tỷ lệ ngữ cảnh quanh mặt của GenD
INPUT_SIZE = 224
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)
SCRFD_SCALE = 128.0  # GenD chia 128 (không phải 127,5 như PAD) và đảo BGR→RGB
TOP_FRACTION = 0.25
BATCH_SIZE = 8
# Ít hơn chừng này khung có mặt (hoặc ít hơn số khung đã lấy, nếu số đó nhỏ hơn) thì điểm không đủ
# tin cậy → `degraded` → review. Hằng số riêng của FACE-02, KHÔNG nằm trong thresholds.yaml.
MIN_VALID_FRAMES = 3
MIN_FACE_SIDE_PX = 2.0

_ALIGN_TARGET = np.array(
    [[0.34, 0.46], [0.66, 0.46], [0.5, 0.64], [0.37, 0.82], [0.63, 0.82]], dtype=np.float32
)


class GendError(PadError):
    """Lỗi hạ tầng của GenD; `code` là ErrorCode sẽ ghi vào ModuleResult."""


class DeepfakeClassifier(Protocol):
    def p_fake(self, batch: np.ndarray) -> list[float]:
        """`batch` float32 [N, 3, 224, 224] đã chuẩn hóa; trả `p_fake` (softmax nhãn 1) mỗi mặt."""
        ...


# ── tiền xử lý (đúng repo GenD) ──────────────────────────────────────────────────────────
def align_face(image: np.ndarray, landmarks: np.ndarray, scale: float = ALIGN_SCALE) -> np.ndarray:
    """Căn mặt theo 5 mốc, `target_size=None` như `detector.py::align_face` của GenD. Trả ảnh BGR vuông."""
    import cv2

    landmarks = np.asarray(landmarks, dtype=np.float32)
    dst = _ALIGN_TARGET.copy()
    desired = np.linalg.norm(landmarks[:, None, :] - landmarks[None, :, :], axis=-1)
    reference = np.linalg.norm(dst[:, None, :] - dst[None, :, :], axis=-1)
    upper = np.triu_indices(len(dst), k=1)
    side = int(np.round(np.mean(desired[upper] / reference[upper]) * scale))
    if side < 1:
        raise GendError("Mốc mặt suy biến.", ErrorCode.E_NO_FACE)
    size = (side, side)
    dst[:, 0] *= size[0]
    dst[:, 1] *= size[1]
    margin = size[0] * (scale - 1) / 2.0
    dst += margin
    dst *= size[0] / (size[0] + 2 * margin)
    matrix = cv2.estimateAffinePartial2D(landmarks, dst, method=cv2.LMEDS)[0]
    if matrix is None:
        raise GendError("Không căn được mặt.", ErrorCode.E_NO_FACE)
    return cv2.warpAffine(image, matrix, size, flags=cv2.INTER_LINEAR)


def to_tensor(aligned_bgr: np.ndarray) -> np.ndarray:
    """BGR → RGB, BICUBIC về 224 (PIL, như CLIPImageProcessor), /255, mean/std CLIP → [3, 224, 224]."""
    from PIL import Image

    rgb = np.ascontiguousarray(aligned_bgr[:, :, ::-1])
    resized = Image.fromarray(rgb).resize((INPUT_SIZE, INPUT_SIZE), Image.BICUBIC)
    pixels = np.asarray(resized, dtype=np.float32) / 255.0
    pixels = (pixels - np.array(CLIP_MEAN, dtype=np.float32)) / np.array(CLIP_STD, dtype=np.float32)
    return np.ascontiguousarray(pixels.transpose(2, 0, 1))


# ── GenD (torch) ─────────────────────────────────────────────────────────────────────────
class GendClassifier:
    """CLIP vision → pooler_output → L2-normalize → Linear(1024, 2) → softmax (nhãn 1 = giả)."""

    def __init__(self, vision, head_weight, head_bias, device) -> None:
        self._vision, self._device = vision, device
        self._weight, self._bias = head_weight, head_bias

    def p_fake(self, batch: np.ndarray) -> list[float]:
        import torch
        import torch.nn.functional as functional

        out: list[float] = []
        with torch.inference_mode():
            for start in range(0, len(batch), BATCH_SIZE):
                pixels = torch.from_numpy(batch[start : start + BATCH_SIZE]).to(self._device)
                features = self._vision(pixel_values=pixels).pooler_output
                logits = functional.linear(
                    functional.normalize(features, p=2, dim=1), self._weight, self._bias
                )
                out.extend(float(v) for v in logits.softmax(dim=-1)[:, 1].cpu())
        return out


def _limit_cpu_threads(target: str) -> None:
    """Chạy CPU thì giới hạn luồng torch (GPU thì không đụng)."""
    if target != "cpu":
        return
    import os

    import torch

    torch.set_num_threads(max(1, min(GEND_CPU_THREADS, os.cpu_count() or 1)))


def _load_classifier(root: Path, device: str | None) -> tuple[GendClassifier, str, str]:
    """Kiểm SHA-256 rồi dựng GenD từ trọng số cục bộ. Trả (bộ phân loại, revision GenD, revision CLIP)."""
    from safetensors.torch import load_file
    from transformers import CLIPVisionConfig, CLIPVisionModel

    _, clip_rev = _verified_weights(root, CLIP_MODEL_ID, CLIP_CONFIG)
    _verified_weights(root, CLIP_MODEL_ID, CLIP_PREPROCESSOR)
    _verified_weights(root, GEND_MODEL_ID, GEND_CONFIG)
    weights, gend_rev = _verified_weights(root, GEND_MODEL_ID, GEND_WEIGHTS)

    config = CLIPVisionConfig.from_pretrained(str(root / CLIP_MODEL_ID), local_files_only=True)
    prefix = "feature_extractor.vision_model."
    tensors = load_file(str(weights))
    vision_state = {
        f"vision_model.{key[len(prefix) :]}": value
        for key, value in tensors.items()
        if key.startswith(prefix)
    }
    head_weight, head_bias = tensors.get("model.linear.weight"), tensors.get("model.linear.bias")
    if head_weight is None or head_bias is None or tuple(head_weight.shape) != (2, 1024):
        raise GendError("Checkpoint GenD thiếu đầu tuyến tính 1024→2.")
    import torch

    # Dựng trên thiết bị `meta` (không cấp phát/khởi tạo ngẫu nhiên 300M tham số) rồi gán thẳng tensor đã
    # nạp (assign=True): đỉnh RAM chỉ còn ~1 bản trọng số thay vì 2, và nạp nhanh hơn.
    with torch.device("meta"):
        vision = CLIPVisionModel(config)
    try:
        vision.load_state_dict(vision_state, strict=True, assign=True)
    except RuntimeError as exc:
        raise GendError("Checkpoint GenD không khớp kiến trúc CLIP ViT-L/14.") from exc
    del tensors, vision_state
    # Buffer không lưu trong checkpoint (position_ids) vẫn ở `meta`: dựng lại đúng như CLIPVisionEmbeddings.
    embeddings = vision.vision_model.embeddings
    embeddings.position_ids = torch.arange(embeddings.num_positions).expand((1, -1))
    if any(t.is_meta for t in (*vision.parameters(), *vision.buffers())):
        raise GendError("Còn tensor chưa được nạp trọng số sau khi dựng GenD.")
    target = resolve_torch_device(device, component="gend")
    vision = vision.to(target).eval()
    _limit_cpu_threads(target)
    return (
        GendClassifier(vision, head_weight.to(target), head_bias.to(target), target),
        gend_rev,
        clip_rev,
    )


# ── Detector ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _FrameScores:
    indices: list[int]
    p_fake: list[float]
    sampled: int


def video_scores(p_fake: list[float]) -> tuple[float, float]:
    """(mean, top25_mean): trung bình, và trung bình của ceil(25%) khung nghi nhất."""
    values = sorted(p_fake, reverse=True)
    top = values[: max(1, math.ceil(TOP_FRACTION * len(values)))]
    return float(np.mean(values)), float(np.mean(top))


class FaceDeepfakeDetector:
    """Bộ phát hiện `face_deepfake` thật. Nạp mô hình một lần (lười hoặc qua `preload`)."""

    name = Module.FACE_DEEPFAKE.value

    def __init__(
        self,
        models_dir: Path | str | None = None,
        *,
        finder: FaceFinder | None = None,
        classifier: DeepfakeClassifier | None = None,
        num_frames: int = EKYC_FRAMES,
    ) -> None:
        self._models_dir = models_dir
        self._finder, self._classifier = finder, classifier
        self._num_frames = num_frames
        self.version = (
            f"gend-clip-l14+scrfd-10g+{AGGREGATION_TAG}"
            if finder is None
            else f"gend-clip-l14+injected+{AGGREGATION_TAG}"
        )
        self._lock = threading.Lock()
        self._loaded_root: Path | None = None

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        with self._lock:
            root = _models_root(models_dir if models_dir is not None else self._models_dir)
            if self._finder is not None and self._classifier is not None:
                if (
                    models_dir is not None
                    and self._loaded_root is not None
                    and root.resolve() != self._loaded_root
                ):
                    raise GendError("GenD đã nạp với MODELS_DIR khác; cần restart.")
                return
            session, det_rev = shared_scrfd_session(root, device)
            classifier, gend_rev, clip_rev = _load_classifier(root, device)
            self._finder = ScrfdFaceFinder(session, scale=SCRFD_SCALE, swap_rb=True)
            self._classifier = classifier
            self._loaded_root = root.resolve()
            self.version = (
                f"gend-clip-l14@{gend_rev[:8]}+clip@{clip_rev[:8]}"
                f"+scrfd-10g@{det_rev[:8]}+{AGGREGATION_TAG}"
            )

    def _largest_face(self, frame: np.ndarray) -> FaceBox | None:
        faces = [
            f
            for f in self._finder.find(frame)
            if f.landmarks is not None
            and f.x2 - f.x1 >= MIN_FACE_SIDE_PX
            and f.y2 - f.y1 >= MIN_FACE_SIDE_PX
        ]
        return max(faces, key=lambda f: f.area) if faces else None

    @property
    def frames_version(self) -> str:
        """Targeted three-view sampling needs its own calibrator, separate from legacy video."""
        return f"{self.version}+{HEAD_VIEWS_TAG}"

    def predict_frames(self, inp: DetectorInput, frames: Mapping[str, np.ndarray]) -> ModuleResult:
        """Score server-selected front/left/right pixels with original GenD preprocessing.

        Ignore inp.video/images/image_roles; no intermediate image files or authentication gate.
        This sampling mode deliberately has a different model_version from predict().
        """
        started = time.perf_counter()

        def result(status: Status, **fields: Any) -> ModuleResult:
            return ModuleResult(
                module=Module.FACE_DEEPFAKE,
                model_version=self.frames_version,
                status=status,
                latency_ms=(time.perf_counter() - started) * 1000,
                **fields,
            )

        try:
            if set(frames) != {"front", "left", "right"}:
                return result(Status.DEGRADED, error_code=ErrorCode.E_CHALLENGE_MISMATCH)
            values = [frames[role] for role in ("front", "left", "right")]
            if any(
                not isinstance(frame, np.ndarray)
                or frame.ndim != 3
                or frame.shape[2] != 3
                or frame.dtype != np.uint8
                or min(frame.shape[:2]) <= 0
                or frame.shape[0] * frame.shape[1] > MAX_VIEW_PIXELS
                for frame in values
            ):
                return result(Status.DEGRADED, error_code=ErrorCode.E_DECODE)
            if len({hashlib.sha256(frame.tobytes()).digest() for frame in values}) != 3:
                return result(Status.DEGRADED, error_code=ErrorCode.E_INTEGRITY)
            self.preload()
            crops = []
            for frame in values:
                faces = self._finder.find(frame)
                if len(faces) != 1:
                    return result(
                        Status.NOT_APPLICABLE,
                        error_code=(ErrorCode.E_NO_FACE if not faces else ErrorCode.E_MULTI_FACE),
                    )
                face = faces[0]
                # Provisional quality bound for selected views; no change to legacy sampling.
                if (
                    face.landmarks is None
                    or min(face.x2 - face.x1, face.y2 - face.y1) < MIN_VIEW_FACE_SIDE_PX
                ):
                    return result(Status.DEGRADED, error_code=ErrorCode.E_LOW_QUALITY)
                crops.append(to_tensor(align_face(frame, np.asarray(face.landmarks))))
            probabilities = self._classifier.p_fake(np.stack(crops))
            if len(probabilities) != 3 or not all(
                math.isfinite(p) and 0 <= p <= 1 for p in probabilities
            ):
                raise GendError("Invalid selected-view scores.")
            mean, top = video_scores(probabilities)
            return result(
                Status.OK,
                score=max(mean, top),
                quality={
                    "frames_sampled": 3,
                    "frames_used": 3,
                    "sampling": HEAD_VIEWS_TAG,
                    "provisional": True,
                },
                evidence=[
                    Evidence(
                        type=EvidenceType.TIMESERIES,
                        name="view_scores",
                        value={
                            role: float(p)
                            for role, p in zip(
                                ("front", "left", "right"), probabilities, strict=True
                            )
                        },
                    ),
                    Evidence(type=EvidenceType.SCALAR, name="mean", value=mean),
                    Evidence(type=EvidenceType.SCALAR, name="top25_mean", value=top),
                    Evidence(
                        type=EvidenceType.TEXT,
                        name="score_scope",
                        value="raw_uncalibrated_not_identity_or_depth",
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

    def _score_frames(self, sampled: Frames, requested: int) -> _FrameScores:
        """Duyệt từng khung (không giữ khung gốc), chỉ giữ crop đã chuẩn hóa. `requested` là số khung
        đã yêu cầu: khung giải mã hỏng hay không có mặt đều tính là thiếu."""
        indices: list[int] = []
        crops: list[np.ndarray] = []
        for index, frame in sampled:
            face = self._largest_face(frame)
            if face is None:
                continue
            try:
                crops.append(to_tensor(align_face(frame, np.array(face.landmarks))))
            except GendError:
                continue
            indices.append(index)
        if not crops:
            return _FrameScores([], [], requested)
        p_fake = self._classifier.p_fake(np.stack(crops))
        if len(p_fake) != len(crops) or not all(math.isfinite(v) for v in p_fake):
            raise GendError("Mô hình trả điểm không hợp lệ.")
        return _FrameScores(indices, p_fake, requested)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = time.perf_counter()

        def result(status: Status, **fields: Any) -> ModuleResult:
            return ModuleResult(
                module=Module.FACE_DEEPFAKE,
                model_version=self.version,
                status=status,
                latency_ms=(time.perf_counter() - started) * 1000,
                **fields,
            )

        try:
            count = (
                FORENSIC_FRAMES if inp.metadata.get("mode") == FORENSIC_MODE else self._num_frames
            )
            if inp.video is not None:
                self.preload()
                requested, sampled = sample_video(Path(inp.video), count)
            elif inp.images:
                self.preload()
                requested, sampled = sample_images(list(inp.images), count)
            else:
                raise GendError("Thiếu video hoặc ảnh mặt.", ErrorCode.E_DECODE)
            scores = self._score_frames(sampled, requested)
            counts = {
                "frames_sampled": float(scores.sampled),
                "frames_used": float(len(scores.p_fake)),
            }
            if not scores.p_fake:
                return result(Status.NOT_APPLICABLE, error_code=ErrorCode.E_NO_FACE, quality=counts)
            mean, top = video_scores(scores.p_fake)
            enough = len(scores.p_fake) >= min(MIN_VALID_FRAMES, scores.sampled)
            return result(
                Status.OK if enough else Status.DEGRADED,
                error_code=None if enough else ErrorCode.E_LOW_QUALITY,
                score=max(mean, top),
                quality=counts,
                evidence=[
                    Evidence(
                        type=EvidenceType.TIMESERIES,
                        name="frame_scores",
                        value=[
                            {"frame": i, "p_fake": round(p, 6)}
                            for i, p in zip(scores.indices, scores.p_fake, strict=True)
                        ],
                        label_vi="Điểm giả mạo theo khung hình (chưa hiệu chỉnh)",
                    ),
                    Evidence(
                        type=EvidenceType.SCALAR,
                        name="mean",
                        value=mean,
                        label_vi="Trung bình các khung (chưa hiệu chỉnh)",
                    ),
                    Evidence(
                        type=EvidenceType.SCALAR,
                        name="top25_mean",
                        value=top,
                        label_vi="Trung bình 25% khung nghi nhất (chưa hiệu chỉnh)",
                    ),
                ],
            )
        except PadError as exc:
            return result(Status.ERROR, error_code=exc.code)
        except Exception:  # noqa: BLE001 - mọi lỗi khác đều thành 'error', không bao giờ là đạt
            return result(Status.ERROR, error_code=ErrorCode.E_INTERNAL)
