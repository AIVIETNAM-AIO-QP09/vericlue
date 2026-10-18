"""FACE-02 (MVP, ADR-0012 mục 1) — cổng chất lượng ảnh mặt phía server, thay mock `quality`.

Luồng: ảnh đầu tiên của phiên (không có ảnh thì khung giữa video) → SCRFD `det_10g` (dùng chung phiên
onnxruntime với `face_pad`/`face_deepfake`, không nạp lần 2) → mặt lớn nhất → đo cỡ mặt (px), độ nét
(phương sai Laplacian trên vùng mặt thu về cỡ cố định), độ sáng (độ chói trung bình vùng mặt), góc
yaw thô (từ 5 mốc), độ lệch tâm. `gate` là `pass` hoặc `fail`; `fail` kèm `error_code` và một
evidence `retry_hint` (mã trong hợp đồng `session.schema.json::RetryHint`, chỉ nói về CHẤT LƯỢNG).

`status` luôn `ok` khi đo được (kể cả khi `gate=fail`, để router cho chụp lại); thiếu ảnh, ảnh hỏng,
thiếu trọng số hay lỗi bất kỳ → `error` (router đưa sang review, không bao giờ coi là đạt).

Các ngưỡng là hằng số có tên bên dưới, TẠM THỜI (ADR-0012 mục 3): chờ ROUT-03 chọn trên `calib_ltt`,
KHÔNG nằm trong `thresholds.yaml`. Mã không gọi mạng.
"""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import (
    ErrorCode,
    Evidence,
    EvidenceType,
    Gate,
    Module,
    ModuleResult,
    Status,
)
from vericlue_ml.face.frames import middle_video_frame
from vericlue_ml.face.pad import (
    SECOND_FACE_AREA_RATIO,
    FaceBox,
    FaceFinder,
    PadError,
    ScrfdFaceFinder,
    _decode,
    _models_root,
    shared_scrfd_session,
)

# ── ngưỡng tạm (chờ ROUT-03) ─────────────────────────────────────────────────────────────
MIN_FACE_PX = 100  # cạnh ngắn của khung mặt, px; nhỏ hơn → MOVE_CLOSER
MAX_FACE_WIDTH_RATIO = 0.85  # bề rộng mặt / bề rộng ảnh; lớn hơn → MOVE_BACK
MAX_CENTER_OFFSET = (
    0.30  # lệch tâm mặt so với tâm ảnh (theo từng chiều, tỷ lệ cạnh ảnh) → FACE_CENTER
)
MAX_CLIPPED_RATIO = 0.10  # phần khung mặt nằm ngoài ảnh (tỷ lệ cạnh mặt) → FACE_CENTER
MIN_ILLUM = 0.20  # độ chói trung bình vùng mặt / 255; thấp hơn → MORE_LIGHT
MIN_SHARPNESS = 60.0  # phương sai Laplacian trên vùng mặt 96×96; thấp hơn → HOLD_STILL (ảnh rõ >= ~160, mờ Gaussian σ=4 ~ 50)
MAX_YAW_DEG = 25.0  # góc quay ngang thô; lớn hơn → FACE_CENTER (hợp đồng chưa có mã "nhìn thẳng")

SHARPNESS_CROP_PX = 96
NOSE_PROTRUSION_RATIO = (
    0.39  # ~25 mm / ~64 mm (mũi nhô ra / khoảng cách hai mắt), ước lượng yaw thô
)
QUALITY_VERSION_BASE = "quality-scrfd-10g"

# Mã retry_hint hợp lệ (packages/contracts/schemas/session.schema.json::RetryHint).
HINT_MORE_LIGHT = "MORE_LIGHT"
HINT_MOVE_CLOSER = "MOVE_CLOSER"
HINT_MOVE_BACK = "MOVE_BACK"
HINT_FACE_CENTER = "FACE_CENTER"
HINT_HOLD_STILL = "HOLD_STILL"

_LABELS_VI = {
    HINT_MORE_LIGHT: "Thiếu sáng",
    HINT_MOVE_CLOSER: "Mặt quá nhỏ",
    HINT_MOVE_BACK: "Mặt quá gần",
    HINT_FACE_CENTER: "Mặt lệch khung, nghiêng hoặc không rõ",
    HINT_HOLD_STILL: "Ảnh bị mờ",
}


class QualityError(PadError):
    """Lỗi hạ tầng của quality; `code` là ErrorCode sẽ ghi vào ModuleResult."""


def yaw_degrees(landmarks: tuple[tuple[float, float], ...]) -> float:
    """Góc yaw thô (độ, dấu theo hướng mũi lệch khỏi giữa hai mắt) từ 5 mốc SCRFD.

    Chiếu mũi lên trục hai mắt (miễn nhiễm với nghiêng đầu), chuẩn hóa theo khoảng cách hai mắt, rồi
    yaw = atan(lệch / NOSE_PROTRUSION_RATIO). Chỉ là ước lượng thô để chặn mặt quay ngang rõ rệt.
    """
    left, right, nose = (np.array(landmarks[i], dtype=np.float64) for i in range(3))
    axis = right - left
    eye_distance = float(np.linalg.norm(axis))
    if eye_distance < 1e-6:
        return 90.0
    offset = float(np.dot(nose - (left + right) / 2.0, axis / eye_distance)) / eye_distance
    return math.degrees(math.atan(offset / NOSE_PROTRUSION_RATIO))


def measure(image: np.ndarray, face: FaceBox) -> dict[str, float]:
    """Các số đo của một mặt trong ảnh BGR: cỡ, độ nét, độ sáng, yaw, vị trí."""
    import cv2

    height, width = image.shape[:2]
    face_w, face_h = face.x2 - face.x1, face.y2 - face.y1
    x1, y1 = max(0, int(face.x1)), max(0, int(face.y1))
    x2, y2 = min(width, int(math.ceil(face.x2))), min(height, int(math.ceil(face.y2)))
    gray = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    crop = cv2.resize(gray, (SHARPNESS_CROP_PX, SHARPNESS_CROP_PX), interpolation=cv2.INTER_AREA)
    clipped_w = max(0.0, -face.x1) + max(0.0, face.x2 - width)
    clipped_h = max(0.0, -face.y1) + max(0.0, face.y2 - height)
    return {
        "face_px": float(min(face_w, face_h)),
        "face_width_ratio": float(face_w / width),
        "sharpness": float(cv2.Laplacian(crop, cv2.CV_64F).var()),
        "illum": float(gray.mean() / 255.0),
        "yaw_deg": yaw_degrees(face.landmarks) if face.landmarks else 0.0,
        "center_offset": float(
            max(
                abs((face.x1 + face.x2) / 2 - width / 2) / width,
                abs((face.y1 + face.y2) / 2 - height / 2) / height,
            )
        ),
        "clipped_ratio": float(max(clipped_w / face_w, clipped_h / face_h)),
    }


def judge(metrics: dict[str, float]) -> str | None:
    """Mã retry_hint của lỗi đầu tiên (theo thứ tự ưu tiên), hoặc None nếu đạt."""
    if metrics["face_px"] < MIN_FACE_PX:
        return HINT_MOVE_CLOSER
    if metrics["face_width_ratio"] > MAX_FACE_WIDTH_RATIO:
        return HINT_MOVE_BACK
    if metrics["clipped_ratio"] > MAX_CLIPPED_RATIO or metrics["center_offset"] > MAX_CENTER_OFFSET:
        return HINT_FACE_CENTER
    if metrics["illum"] < MIN_ILLUM:
        return HINT_MORE_LIGHT
    if metrics["sharpness"] < MIN_SHARPNESS:
        return HINT_HOLD_STILL
    if abs(metrics["yaw_deg"]) > MAX_YAW_DEG:
        return HINT_FACE_CENTER
    return None


class QualityDetector:
    """Bộ phát hiện `quality` thật. Dùng chung phiên SCRFD với các module mặt khác."""

    name = Module.QUALITY.value

    def __init__(
        self, models_dir: Path | str | None = None, *, finder: FaceFinder | None = None
    ) -> None:
        self._models_dir = models_dir
        self._finder = finder
        self.version = QUALITY_VERSION_BASE if finder is None else "quality-injected"
        self._lock = threading.Lock()
        self._loaded_root: Path | None = None

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        with self._lock:
            root = _models_root(models_dir if models_dir is not None else self._models_dir)
            if self._finder is not None:
                if (
                    models_dir is not None
                    and self._loaded_root is not None
                    and root.resolve() != self._loaded_root
                ):
                    raise QualityError("quality đã nạp với MODELS_DIR khác; cần restart.")
                return
            session, revision = shared_scrfd_session(root, device)
            self._finder = ScrfdFaceFinder(session)
            self._loaded_root = root.resolve()
            self.version = f"{QUALITY_VERSION_BASE}@{revision[:8]}"

    @staticmethod
    def _image(inp: DetectorInput) -> np.ndarray:
        if inp.images:
            return _decode(Path(inp.images[0]))
        if inp.video is not None:
            return middle_video_frame(Path(inp.video))
        raise QualityError("Thiếu ảnh mặt.", ErrorCode.E_DECODE)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = time.perf_counter()

        def result(status: Status, **fields: Any) -> ModuleResult:
            return ModuleResult(
                module=Module.QUALITY,
                model_version=self.version,
                status=status,
                latency_ms=(time.perf_counter() - started) * 1000,
                **fields,
            )

        def failed(hint: str, code: ErrorCode, quality: dict[str, float]) -> ModuleResult:
            return result(
                Status.OK,
                gate=Gate.FAIL,
                error_code=code,
                quality=quality,
                evidence=[
                    Evidence(
                        type=EvidenceType.TEXT,
                        name="retry_hint",
                        value=hint,
                        label_vi=_LABELS_VI[hint],
                    )
                ],
            )

        try:
            image = self._image(inp)
            self.preload()
            faces = sorted(self._finder.find(image), key=lambda f: f.area, reverse=True)
            if not faces:
                return failed(HINT_FACE_CENTER, ErrorCode.E_NO_FACE, {"faces": 0.0})
            largest = faces[0]
            if largest.x2 - largest.x1 < 2 or largest.y2 - largest.y1 < 2:
                return failed(HINT_MOVE_CLOSER, ErrorCode.E_NO_FACE, {"faces": float(len(faces))})
            if len(faces) > 1 and faces[1].area >= SECOND_FACE_AREA_RATIO * largest.area:
                return failed(
                    HINT_FACE_CENTER, ErrorCode.E_MULTI_FACE, {"faces": float(len(faces))}
                )
            metrics = {"faces": float(len(faces)), **measure(image, largest)}
            hint = judge(metrics)
            if hint is not None:
                return failed(hint, ErrorCode.E_LOW_QUALITY, metrics)
            return result(Status.OK, gate=Gate.PASS, quality=metrics)
        except PadError as exc:
            return result(Status.ERROR, error_code=exc.code)
        except Exception:  # noqa: BLE001 - mọi lỗi khác đều thành 'error', không bao giờ là đạt
            return result(Status.ERROR, error_code=ErrorCode.E_INTERNAL)
