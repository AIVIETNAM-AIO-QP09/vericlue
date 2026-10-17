"""FACE-01 — PAD (chống ảnh in / màn hình phát lại) bằng MiniFASNet V2 chạy qua onnxruntime.

Luồng: ảnh → SCRFD `det_10g` tìm mặt → cắt vùng quanh mặt (hệ số 2,7) → MiniFASNet → softmax →
`prob_attack = 1 - p_real`. Không có mặt → `not_applicable`; hai mặt cỡ tương đương → `degraded`
(không bao giờ được coi là đạt); thiếu trọng số, sai SHA-256 hay lỗi bất kỳ → `error`.

Trọng số đọc từ `MODELS_DIR/<id trong models/manifest.yaml>/<file>` và kiểm SHA-256 theo manifest.
Mã KHÔNG gọi mạng. `prob_attack` ở đây CHƯA hiệu chỉnh (calibration thuộc FACE-04 / ROUT-*).

Nguồn tiền xử lý và giải mã (chép lại, giữ giấy phép — xem `third_party/README.md`):
- uniface 4.0.0 (MIT, Copyright 2025-2026 Yakhyokhuja Valikhujaev, https://github.com/yakhyo/uniface):
  `uniface/spoofing/minifasnet.py` (cắt theo `scale`, float32 không chuẩn hóa, NCHW, softmax;
  nhãn 1 = thật) và `uniface/detection/scrfd.py` + `uniface/common.py` (letterbox 640, chuẩn hóa
  (x-127,5)/127,5, giải mã anchor 3 tầng stride 8/16/32 × 2 anchor, NMS 0,4, ngưỡng 0,5).
- SCRFD: "Sample and Computation Redistribution for Efficient Face Detection"
  (insightface). Trọng số `det_10g.onnx` là giấy phép NGHIÊN CỨU PHI THƯƠNG MẠI.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import yaml

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import (
    ErrorCode,
    Evidence,
    EvidenceType,
    Module,
    ModuleResult,
    Status,
)

REPO_ROOT = Path(__file__).resolve().parents[4]

PAD_MODEL_ID = "minifasnet"
DETECTOR_MODEL_ID = "scrfd-10g"
PAD_FILE = "minifasnet_v2.onnx"
DETECTOR_FILE = "det_10g.onnx"

# Mặt thứ hai nhỏ hơn rõ rệt (diện tích < 50% mặt lớn nhất, ví dụ ảnh trên CCCD hoặc người ở xa)
# thì bỏ qua và dùng mặt lớn nhất. Hằng số riêng của FACE-01, KHÔNG nằm trong thresholds.yaml.
SECOND_FACE_AREA_RATIO = 0.5

PAD_CROP_SCALE = 2.7  # MiniFASNet V2 (uniface DEFAULT_SCALES)
DET_INPUT_SIZE = 640
DET_CONFIDENCE = 0.5
DET_NMS = 0.4
_STRIDES = (8, 16, 32)
_ANCHORS_PER_CELL = 2


class PadError(Exception):
    """Lỗi hạ tầng của PAD; `code` là ErrorCode sẽ ghi vào ModuleResult."""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.E_INTERNAL) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FaceBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


class FaceFinder(Protocol):
    def find(self, image: np.ndarray) -> list[FaceBox]: ...


class SpoofClassifier(Protocol):
    def p_real(self, image: np.ndarray, box: FaceBox) -> float: ...


# ── trọng số ─────────────────────────────────────────────────────────────────────────────
def _models_root(models_dir: Path | str | None) -> Path:
    root = Path(models_dir or os.environ.get("MODELS_DIR") or REPO_ROOT / "models")
    return root if root.is_absolute() else REPO_ROOT / root


def _manifest_entry(model_id: str, filename: str) -> dict[str, Any]:
    path = Path(os.environ.get("ML_MODELS_MANIFEST") or REPO_ROOT / "models" / "manifest.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for model in data.get("models", []):
        if model.get("id") == model_id:
            for file in model.get("files", []):
                if file.get("path") == filename:
                    return {**file, "revision": model.get("source", {}).get("revision", "")}
    raise PadError(f"Manifest không có {model_id}/{filename}.")


def _verified_weights(root: Path, model_id: str, filename: str) -> tuple[Path, str]:
    """Trả (đường dẫn file, revision). Thiếu file hoặc sai SHA-256 thì ném PadError — không tải."""
    entry = _manifest_entry(model_id, filename)
    path = root / model_id / filename
    if not path.is_file():
        raise PadError(f"Thiếu trọng số {model_id}/{filename}; chạy scripts/download_models.py.")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != entry["sha256"]:
        raise PadError(f"SHA-256 của {model_id}/{filename} sai.", ErrorCode.E_INTEGRITY)
    return path, str(entry["revision"])


def _providers(device: str | None = None) -> list[str]:
    """CPU luôn chạy được; có CUDA thì ưu tiên, trừ khi `DEVICE=cpu`."""
    import onnxruntime as ort

    if (device or os.environ.get("DEVICE") or "auto").strip().lower() == "cpu":
        return ["CPUExecutionProvider"]
    available = ort.get_available_providers()
    return [p for p in ("CUDAExecutionProvider",) if p in available] + ["CPUExecutionProvider"]


def _session(path: Path, device: str | None = None):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.log_severity_level = 3
    return ort.InferenceSession(str(path), sess_options=options, providers=_providers(device))


# ── SCRFD (tìm mặt) ──────────────────────────────────────────────────────────────────────
def _letterbox(image: np.ndarray, size: int) -> tuple[np.ndarray, float]:
    import cv2

    height, width = image.shape[:2]
    ratio = height / width
    if ratio > 1.0:
        new_h, new_w = size, int(size / ratio)
    else:
        new_w, new_h = size, int(size * ratio)
    factor = new_h / height
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    canvas[:new_h, :new_w] = cv2.resize(image, (new_w, new_h))
    return canvas, factor


def _nms(dets: np.ndarray, threshold: float) -> list[int]:
    x1, y1, x2, y2, scores = dets.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        overlap = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(overlap <= threshold)[0] + 1]
    return keep


class ScrfdFaceFinder:
    def __init__(self, session) -> None:
        self._session = session
        self._input = session.get_inputs()[0].name
        self._outputs = [o.name for o in session.get_outputs()]
        if len(self._outputs) != 9:
            raise PadError("det_10g.onnx không có 9 đầu ra (3 tầng × điểm, hộp, mốc mặt).")
        self._centers: dict[tuple[int, int], np.ndarray] = {}

    def _anchor_centers(self, cells: int, stride: int) -> np.ndarray:
        key = (cells, stride)
        if key not in self._centers:
            y, x = np.mgrid[:cells, :cells]
            centers = (np.stack((x, y), axis=-1).astype(np.float32) * stride).reshape(-1, 2)
            self._centers[key] = np.tile(centers[:, None, :], (1, _ANCHORS_PER_CELL, 1)).reshape(
                -1, 2
            )
        return self._centers[key]

    def find(self, image: np.ndarray) -> list[FaceBox]:
        canvas, factor = _letterbox(image, DET_INPUT_SIZE)
        tensor = ((canvas.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
        outputs = self._session.run(self._outputs, {self._input: tensor})
        boxes: list[np.ndarray] = []
        scores: list[np.ndarray] = []
        for index, stride in enumerate(_STRIDES):
            score = outputs[index]
            distance = outputs[len(_STRIDES) + index] * stride
            keep = np.where(score >= DET_CONFIDENCE)[0]
            if keep.size == 0:
                continue
            centers = self._anchor_centers(DET_INPUT_SIZE // stride, stride)
            decoded = np.stack(
                [
                    centers[:, 0] - distance[:, 0],
                    centers[:, 1] - distance[:, 1],
                    centers[:, 0] + distance[:, 2],
                    centers[:, 1] + distance[:, 3],
                ],
                axis=-1,
            )
            boxes.append(decoded[keep])
            scores.append(score[keep])
        if not boxes:
            return []
        all_scores = np.vstack(scores)
        order = all_scores.ravel().argsort()[::-1]
        dets = np.hstack((np.vstack(boxes) / factor, all_scores)).astype(np.float32)[order]
        kept = dets[_nms(dets, DET_NMS)]
        return [FaceBox(*(float(v) for v in row)) for row in kept]


# ── MiniFASNet (PAD) ─────────────────────────────────────────────────────────────────────
def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e / np.sum(e, axis=-1, keepdims=True)


class MiniFasNetClassifier:
    def __init__(self, session, scale: float = PAD_CROP_SCALE) -> None:
        self._session = session
        self._input = session.get_inputs()[0].name
        self._output = session.get_outputs()[0].name
        height, width = session.get_inputs()[0].shape[2:4]
        self._size = (int(width), int(height))
        self._scale = scale

    def _crop(self, image: np.ndarray, box: FaceBox) -> np.ndarray:
        import cv2

        src_h, src_w = image.shape[:2]
        x, y = int(box.x1), int(box.y1)
        box_w, box_h = int(box.x2 - box.x1), int(box.y2 - box.y1)
        scale = min((src_h - 1) / box_h, (src_w - 1) / box_w, self._scale)
        new_w, new_h = box_w * scale, box_h * scale
        cx, cy = x + box_w / 2, y + box_h / 2
        x1, y1 = max(0, int(cx - new_w / 2)), max(0, int(cy - new_h / 2))
        x2, y2 = min(src_w - 1, int(cx + new_w / 2)), min(src_h - 1, int(cy + new_h / 2))
        return cv2.resize(image[y1 : y2 + 1, x1 : x2 + 1], self._size)

    def p_real(self, image: np.ndarray, box: FaceBox) -> float:
        face = self._crop(image, box).astype(np.float32)  # BGR, không chuẩn hóa
        tensor = np.expand_dims(np.transpose(face, (2, 0, 1)), axis=0)
        logits = self._session.run([self._output], {self._input: tensor})[0]
        return float(_softmax(logits)[0, 1])  # nhãn 1 = thật


# ── Detector ─────────────────────────────────────────────────────────────────────────────
def _decode(path: Path) -> np.ndarray:
    import cv2

    try:
        data = np.fromfile(str(path), dtype=np.uint8)  # đường dẫn Unicode trên Windows
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception as exc:
        raise PadError("Không đọc được ảnh.", ErrorCode.E_DECODE) from exc
    if image is None or image.size == 0:
        raise PadError("Không giải mã được ảnh.", ErrorCode.E_DECODE)
    return image


class FacePadDetector:
    """Bộ phát hiện `face_pad` thật. Nạp mô hình một lần (lười hoặc qua `preload`)."""

    name = Module.FACE_PAD.value

    def __init__(
        self,
        models_dir: Path | str | None = None,
        *,
        finder: FaceFinder | None = None,
        classifier: SpoofClassifier | None = None,
    ) -> None:
        self._models_dir = models_dir
        self._finder, self._classifier = finder, classifier
        self.version = "minifasnet-v2+scrfd-10g" if finder is None else "minifasnet-v2+injected"
        self._lock = threading.Lock()

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        with self._lock:
            if self._finder is not None and self._classifier is not None:
                return
            root = _models_root(models_dir if models_dir is not None else self._models_dir)
            pad_path, pad_rev = _verified_weights(root, PAD_MODEL_ID, PAD_FILE)
            det_path, det_rev = _verified_weights(root, DETECTOR_MODEL_ID, DETECTOR_FILE)
            self._classifier = MiniFasNetClassifier(_session(pad_path, device))
            self._finder = ScrfdFaceFinder(_session(det_path, device))
            self.version = f"minifasnet-v2@{pad_rev[:8]}+scrfd-10g@{det_rev[:8]}"

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = time.perf_counter()

        def result(status: Status, **fields: Any) -> ModuleResult:
            return ModuleResult(
                module=Module.FACE_PAD,
                model_version=self.version,
                status=status,
                latency_ms=(time.perf_counter() - started) * 1000,
                **fields,
            )

        try:
            if not inp.images:
                raise PadError("Thiếu ảnh mặt.", ErrorCode.E_DECODE)
            self.preload()
            image = _decode(inp.images[0])
            faces = self._finder.find(image)
            if not faces:
                return result(Status.NOT_APPLICABLE, error_code=ErrorCode.E_NO_FACE)
            faces = sorted(faces, key=lambda f: f.area, reverse=True)
            largest = faces[0]
            if len(faces) > 1 and faces[1].area >= SECOND_FACE_AREA_RATIO * largest.area:
                return result(
                    Status.DEGRADED,
                    error_code=ErrorCode.E_MULTI_FACE,
                    quality={"faces": float(len(faces))},
                )
            if largest.x2 - largest.x1 < 2 or largest.y2 - largest.y1 < 2:
                return result(Status.NOT_APPLICABLE, error_code=ErrorCode.E_NO_FACE)
            p_real = self._classifier.p_real(image, largest)
            if not np.isfinite(p_real):
                raise PadError("Mô hình trả điểm không hợp lệ.")
            height, width = image.shape[:2]
            return result(
                Status.OK,
                score=1.0 - p_real,
                prob_attack=min(1.0, max(0.0, 1.0 - p_real)),
                quality={
                    "faces": float(len(faces)),
                    "face_area_ratio": largest.area / float(height * width),
                    "det_confidence": largest.confidence,
                },
                evidence=[
                    Evidence(
                        type=EvidenceType.SCALAR,
                        name="p_real",
                        value=p_real,
                        label_vi="Xác suất ảnh là mặt thật (chưa hiệu chỉnh)",
                    )
                ],
            )
        except PadError as exc:
            return result(Status.ERROR, error_code=exc.code)
        except Exception:  # noqa: BLE001 - mọi lỗi khác đều thành 'error', không bao giờ là đạt
            return result(Status.ERROR, error_code=ErrorCode.E_INTERNAL)
