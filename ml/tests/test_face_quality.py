"""FACE-02 quality: cổng chất lượng ảnh mặt với finder giả — không cần GPU, trọng số hay mạng.

Mọi ngưỡng lấy từ hằng số trong `quality.py` (có thể được chỉnh ở ROUT-03), không hard-code số.
"""

from __future__ import annotations

import json
import math
import socket
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from vericlue_ml.common import DetectorInput, ErrorCode, Module, Status
from vericlue_ml.common.result import EvidenceType, Gate
from vericlue_ml.face import pad, quality
from vericlue_ml.face.pad import SECOND_FACE_AREA_RATIO, FaceBox
from vericlue_ml.face.quality import (
    MAX_CENTER_OFFSET,
    MAX_CLIPPED_RATIO,
    MAX_FACE_WIDTH_RATIO,
    MAX_YAW_DEG,
    MIN_FACE_PX,
    MIN_ILLUM,
    MIN_SHARPNESS,
    NOSE_PROTRUSION_RATIO,
    QualityDetector,
    QualityError,
    judge,
    measure,
    yaw_degrees,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "packages/contracts/schemas"
SCHEMA = json.loads((SCHEMAS / "module_result.schema.json").read_text(encoding="utf-8"))
SESSION_SCHEMA = json.loads((SCHEMAS / "session.schema.json").read_text(encoding="utf-8"))
RETRY_HINTS = {h for h in SESSION_SCHEMA["$defs"]["RetryHint"]["enum"] if h is not None}

cv2 = pytest.importorskip("cv2")

CANVAS = 4 * MIN_FACE_PX  # ảnh vuông đủ lớn cho một mặt cỡ 2 × MIN_FACE_PX
GOOD_SIZE = 2 * MIN_FACE_PX


class FakeFinder:
    def __init__(self, boxes: list[FaceBox]) -> None:
        self.boxes = boxes
        self.seen: list[np.ndarray] = []

    def find(self, image: np.ndarray) -> list[FaceBox]:
        self.seen.append(image)
        return list(self.boxes)


class BoomFinder:
    def find(self, image: np.ndarray) -> list[FaceBox]:
        raise RuntimeError("boom")


# ── dựng dữ liệu ─────────────────────────────────────────────────────────────────────────
def landmarks(cx: float, cy: float, size: float, nose_shift: float = 0.0, tilt_deg: float = 0.0):
    """5 mốc của mặt nhìn thẳng trong khung vuông `size` tâm (cx, cy).

    `nose_shift`: mũi lệch sang phải theo tỷ lệ khoảng cách hai mắt; `tilt_deg`: xoay cả 5 mốc quanh tâm.
    """
    eye = 0.4 * size
    pts = [
        (-eye / 2, -0.1 * size),  # mắt trái
        (eye / 2, -0.1 * size),  # mắt phải
        (nose_shift * eye, 0.05 * size),  # mũi
        (-0.15 * size, 0.25 * size),  # miệng trái
        (0.15 * size, 0.25 * size),  # miệng phải
    ]
    c, s = math.cos(math.radians(tilt_deg)), math.sin(math.radians(tilt_deg))
    return tuple((cx + c * x - s * y, cy + s * x + c * y) for x, y in pts)


def box(
    size: float = GOOD_SIZE,
    *,
    cx: float = CANVAS / 2,
    cy: float = CANVAS / 2,
    nose_shift: float = 0.0,
    conf: float = 0.9,
) -> FaceBox:
    return FaceBox(
        cx - size / 2,
        cy - size / 2,
        cx + size / 2,
        cy + size / 2,
        conf,
        landmarks(cx, cy, size, nose_shift),
    )


def noise_image(
    width: int = CANVAS, height: int = CANVAS, *, level: float = 0.5, blur: bool = False
) -> np.ndarray:
    """Nhiễu nhị phân {0, v} cố định seed: độ chói trung bình ≈ level, rất nét; blur → gần phẳng."""
    value = min(255, round(2 * level * 255))
    rng = np.random.default_rng(0)
    gray = (rng.integers(0, 2, (height, width), dtype=np.uint8) * value).astype(np.uint8)
    image = np.repeat(gray[:, :, None], 3, axis=2)
    return cv2.GaussianBlur(image, (0, 0), sigmaX=25) if blur else image


def write(tmp_path: Path, image: np.ndarray, name: str = "face.png") -> Path:
    path = tmp_path / name
    assert cv2.imwrite(str(path), image)
    return path


def run(boxes, path):
    return QualityDetector(finder=FakeFinder(boxes)).predict(DetectorInput(images=[path]))


def valid(result) -> None:
    jsonschema.validate(result.to_contract(), SCHEMA)


def hints(result) -> list[str]:
    return [e.value for e in result.evidence if e.name == "retry_hint"]


def assert_fail(result, hint: str, code: ErrorCode = ErrorCode.E_LOW_QUALITY) -> None:
    assert result.module == Module.QUALITY.value
    assert result.status == Status.OK and result.is_usable
    assert result.gate == Gate.FAIL
    assert result.error_code == code
    assert hints(result) == [hint]
    (evidence,) = result.evidence
    assert evidence.type == EvidenceType.TEXT
    assert hint in RETRY_HINTS
    assert evidence.label_vi
    valid(result)


# Bộ số đo "tốt", dùng cho judge()
GOOD_METRICS = {
    "face_px": float(2 * MIN_FACE_PX),
    "face_width_ratio": 0.5 * MAX_FACE_WIDTH_RATIO,
    "sharpness": 10 * MIN_SHARPNESS,
    "illum": MIN_ILLUM + 0.3,
    "yaw_deg": 0.0,
    "center_offset": 0.0,
    "clipped_ratio": 0.0,
}


# ── 1. ảnh tốt ───────────────────────────────────────────────────────────────────────────
def test_good_image_passes(tmp_path):
    path = write(tmp_path, noise_image())
    r = run([box()], path)
    assert r.module == Module.QUALITY.value
    assert r.status == Status.OK and r.is_usable
    assert r.gate == Gate.PASS
    assert r.error_code is None
    assert hints(r) == [] and r.evidence == []
    assert r.score is None and r.prob_attack is None
    assert isinstance(r.model_version, str) and r.model_version
    assert r.latency_ms >= 0
    for key in (
        "faces",
        "face_px",
        "face_width_ratio",
        "sharpness",
        "illum",
        "yaw_deg",
        "center_offset",
        "clipped_ratio",
    ):
        assert isinstance(r.quality[key], float), key
    assert r.quality["faces"] == 1.0
    assert r.quality["face_px"] == pytest.approx(GOOD_SIZE)
    assert r.quality["yaw_deg"] == pytest.approx(0.0, abs=1e-6)
    assert r.quality["clipped_ratio"] == 0.0
    valid(r)


# ── 2. mỗi lỗi → gate fail + retry_hint đúng ─────────────────────────────────────────────
def test_small_face_move_closer(tmp_path):
    path = write(tmp_path, noise_image())
    r = run([box(MIN_FACE_PX - 10)], path)
    assert_fail(r, "MOVE_CLOSER")
    assert r.quality["face_px"] < MIN_FACE_PX


def test_face_at_exact_min_size_is_not_too_small(tmp_path):
    path = write(tmp_path, noise_image())
    r = run([box(MIN_FACE_PX)], path)
    assert r.gate == Gate.PASS


def test_too_wide_face_move_back(tmp_path):
    size = (MAX_FACE_WIDTH_RATIO + 0.05) * CANVAS
    path = write(tmp_path, noise_image())
    r = run([box(size)], path)
    assert_fail(r, "MOVE_BACK")
    assert r.quality["face_width_ratio"] > MAX_FACE_WIDTH_RATIO
    assert r.quality["clipped_ratio"] <= MAX_CLIPPED_RATIO  # chỉ lỗi "quá gần"


def test_dark_face_more_light(tmp_path):
    path = write(tmp_path, noise_image(level=MIN_ILLUM / 2))
    r = run([box()], path)
    assert_fail(r, "MORE_LIGHT")
    assert r.quality["illum"] < MIN_ILLUM


def test_blurry_face_hold_still(tmp_path):
    path = write(tmp_path, noise_image(blur=True))
    r = run([box()], path)
    assert_fail(r, "HOLD_STILL")
    assert r.quality["sharpness"] < MIN_SHARPNESS
    assert r.quality["illum"] >= MIN_ILLUM  # chỉ lỗi "mờ"


def test_off_center_face_face_center(tmp_path):
    # ảnh rộng để mặt lệch ngang mà vẫn nằm trọn trong ảnh (không bị cắt)
    width = 16 * MIN_FACE_PX
    cx = (0.5 + MAX_CENTER_OFFSET + 0.05) * width
    path = write(tmp_path, noise_image(width, CANVAS))
    r = run([box(cx=cx)], path)
    assert_fail(r, "FACE_CENTER")
    assert r.quality["center_offset"] > MAX_CENTER_OFFSET
    assert r.quality["clipped_ratio"] <= MAX_CLIPPED_RATIO


def test_clipped_face_face_center(tmp_path):
    size = GOOD_SIZE
    # nhô khỏi mép phải một phần (MAX_CLIPPED_RATIO + 0.1) cạnh mặt
    x2 = CANVAS + (MAX_CLIPPED_RATIO + 0.1) * size
    b = box(size, cx=x2 - size / 2)
    path = write(tmp_path, noise_image())
    r = run([b], path)
    assert_fail(r, "FACE_CENTER")
    assert r.quality["clipped_ratio"] > MAX_CLIPPED_RATIO


def test_large_yaw_face_center(tmp_path):
    shift = math.tan(math.radians(MAX_YAW_DEG + 10)) * NOSE_PROTRUSION_RATIO
    path = write(tmp_path, noise_image())
    r = run([box(nose_shift=shift)], path)
    assert_fail(r, "FACE_CENTER")
    assert abs(r.quality["yaw_deg"]) > MAX_YAW_DEG
    assert r.quality["center_offset"] <= MAX_CENTER_OFFSET


def test_small_yaw_still_passes(tmp_path):
    shift = math.tan(math.radians(MAX_YAW_DEG / 2)) * NOSE_PROTRUSION_RATIO
    path = write(tmp_path, noise_image())
    assert run([box(nose_shift=shift)], path).gate == Gate.PASS


def test_face_without_landmarks_has_zero_yaw(tmp_path):
    b = box()
    b = FaceBox(b.x1, b.y1, b.x2, b.y2, b.confidence)
    r = run([b], write(tmp_path, noise_image()))
    assert r.gate == Gate.PASS and r.quality["yaw_deg"] == 0.0


# ── 3. thứ tự ưu tiên ────────────────────────────────────────────────────────────────────
FAULTS = [  # đúng thứ tự ưu tiên của judge()
    ("MOVE_CLOSER", {"face_px": MIN_FACE_PX - 10.0}),
    ("MOVE_BACK", {"face_width_ratio": MAX_FACE_WIDTH_RATIO + 0.05}),
    ("FACE_CENTER", {"clipped_ratio": MAX_CLIPPED_RATIO + 0.1}),
    ("FACE_CENTER", {"center_offset": MAX_CENTER_OFFSET + 0.1}),
    ("MORE_LIGHT", {"illum": MIN_ILLUM / 2}),
    ("HOLD_STILL", {"sharpness": MIN_SHARPNESS / 2}),
    ("FACE_CENTER", {"yaw_deg": MAX_YAW_DEG + 10}),
]


def test_judge_good_metrics_pass():
    assert judge(GOOD_METRICS) is None


@pytest.mark.parametrize("hint,override", FAULTS)
def test_judge_single_fault(hint, override):
    assert judge({**GOOD_METRICS, **override}) == hint


@pytest.mark.parametrize("index", range(len(FAULTS)))
def test_judge_priority_when_several_faults(index):
    merged: dict[str, float] = {}
    for _, override in FAULTS[index:]:
        merged.update(override)
    assert judge({**GOOD_METRICS, **merged}) == FAULTS[index][0]


def test_judge_negative_yaw_also_fails():
    assert judge({**GOOD_METRICS, "yaw_deg": -(MAX_YAW_DEG + 10)}) == "FACE_CENTER"


def test_predict_priority_small_dark_blurry_face(tmp_path):
    path = write(tmp_path, noise_image(level=MIN_ILLUM / 2, blur=True))
    r = run([box(MIN_FACE_PX - 10)], path)
    assert_fail(r, "MOVE_CLOSER")


def test_predict_priority_dark_beats_blurry(tmp_path):
    path = write(tmp_path, noise_image(level=MIN_ILLUM / 2, blur=True))
    r = run([box()], path)
    assert_fail(r, "MORE_LIGHT")
    assert r.quality["sharpness"] < MIN_SHARPNESS


# ── 4. số mặt ────────────────────────────────────────────────────────────────────────────
def test_no_face(tmp_path):
    r = run([], write(tmp_path, noise_image()))
    assert_fail(r, "FACE_CENTER", ErrorCode.E_NO_FACE)
    assert r.quality == {"faces": 0.0}


def test_degenerate_tiny_box_is_no_face(tmp_path):
    r = run([FaceBox(10, 10, 11, 11, 0.9)], write(tmp_path, noise_image()))
    assert_fail(r, "MOVE_CLOSER", ErrorCode.E_NO_FACE)


def test_two_equal_faces_multi_face(tmp_path):
    boxes = [box(GOOD_SIZE, cx=CANVAS / 4), box(GOOD_SIZE, cx=3 * CANVAS / 4)]
    r = run(boxes, write(tmp_path, noise_image()))
    assert_fail(r, "FACE_CENTER", ErrorCode.E_MULTI_FACE)
    assert r.quality == {"faces": 2.0}


def test_second_face_just_above_ratio_is_multi_face(tmp_path):
    second = GOOD_SIZE * math.sqrt(SECOND_FACE_AREA_RATIO + 0.05)
    boxes = [box(GOOD_SIZE, cx=CANVAS / 4), box(second, cx=3 * CANVAS / 4)]
    r = run(boxes, write(tmp_path, noise_image()))
    assert_fail(r, "FACE_CENTER", ErrorCode.E_MULTI_FACE)


def test_much_smaller_second_face_is_ignored(tmp_path):
    second = GOOD_SIZE * math.sqrt(SECOND_FACE_AREA_RATIO - 0.1)
    big = box(GOOD_SIZE)
    small = box(second, cx=second / 2 + 1, cy=second / 2 + 1)
    r = run(
        [small, big], write(tmp_path, noise_image())
    )  # mặt nhỏ đứng trước: vẫn dùng mặt lớn nhất
    assert r.status == Status.OK and r.gate == Gate.PASS
    assert r.quality["faces"] == 2.0
    assert r.quality["face_px"] == pytest.approx(GOOD_SIZE)
    assert r.quality["center_offset"] == pytest.approx(0.0)
    valid(r)


# ── 5. yaw_degrees ───────────────────────────────────────────────────────────────────────
def test_yaw_frontal_is_zero():
    assert yaw_degrees(landmarks(100, 100, 100)) == pytest.approx(0.0, abs=1e-9)


def test_yaw_sign_and_monotonic_in_nose_offset():
    shifts = [0.1, 0.2, 0.4, 0.8]
    right = [yaw_degrees(landmarks(100, 100, 100, nose_shift=s)) for s in shifts]
    left = [yaw_degrees(landmarks(100, 100, 100, nose_shift=-s)) for s in shifts]
    assert all(v > 0 for v in right) and all(v < 0 for v in left)
    assert right == sorted(right) and left == sorted(left, reverse=True)
    for r_, l_ in zip(right, left, strict=True):
        assert r_ == pytest.approx(-l_)
    assert all(abs(v) < 90 for v in right)


def test_yaw_known_value():
    # mũi lệch đúng NOSE_PROTRUSION_RATIO × khoảng cách hai mắt → 45°
    assert yaw_degrees(landmarks(0, 0, 100, nose_shift=NOSE_PROTRUSION_RATIO)) == pytest.approx(
        45.0
    )


@pytest.mark.parametrize("tilt", [-30.0, -10.0, 10.0, 30.0])
@pytest.mark.parametrize("shift", [0.0, 0.3])
def test_yaw_invariant_to_head_tilt(tilt, shift):
    base = yaw_degrees(landmarks(100, 100, 100, nose_shift=shift))
    tilted = yaw_degrees(landmarks(100, 100, 100, nose_shift=shift, tilt_deg=tilt))
    assert tilted == pytest.approx(base, abs=1e-6)


def test_yaw_coincident_eyes_is_ninety():
    pts = ((50.0, 50.0), (50.0, 50.0), (60.0, 60.0), (45.0, 70.0), (55.0, 70.0))
    assert yaw_degrees(pts) == 90.0


# ── 6. measure ───────────────────────────────────────────────────────────────────────────
def test_measure_flat_gray_image():
    level = 51
    image = np.full((200, 300, 3), level, np.uint8)
    m = measure(image, FaceBox(100, 50, 200, 150, 0.9, landmarks(150, 100, 100)))
    assert m["face_px"] == 100.0
    assert m["face_width_ratio"] == pytest.approx(100 / 300)
    assert m["illum"] == pytest.approx(level / 255)
    assert m["sharpness"] == pytest.approx(0.0, abs=1e-6)
    assert m["yaw_deg"] == pytest.approx(0.0, abs=1e-6)
    assert m["center_offset"] == pytest.approx(0.0)
    assert m["clipped_ratio"] == 0.0


def test_measure_face_px_is_shorter_side():
    image = np.full((200, 300, 3), 100, np.uint8)
    m = measure(image, FaceBox(10, 10, 130, 90, 0.9))  # 120 × 80
    assert m["face_px"] == 80.0
    assert m["face_width_ratio"] == pytest.approx(120 / 300)


def test_measure_illum_uses_face_region_only():
    image = np.zeros((200, 300, 3), np.uint8)
    image[:, 150:] = 255
    assert measure(image, FaceBox(160, 50, 260, 150, 0.9))["illum"] == pytest.approx(1.0)
    assert measure(image, FaceBox(10, 50, 110, 150, 0.9))["illum"] == pytest.approx(0.0)


def test_measure_sharp_vs_blur():
    sharp = measure(noise_image(), box())["sharpness"]
    blurred = measure(noise_image(blur=True), box())["sharpness"]
    assert sharp > MIN_SHARPNESS > blurred


def test_measure_center_offset_and_clipping():
    image = np.full((200, 300, 3), 100, np.uint8)
    m = measure(image, FaceBox(-20, 50, 80, 150, 0.9))  # 20 px nhô ra mép trái
    assert m["clipped_ratio"] == pytest.approx(0.2)
    assert m["center_offset"] == pytest.approx(abs(30 - 150) / 300)
    m = measure(image, FaceBox(250, 100, 350, 200, 0.9))  # nhô 50 px mép phải
    assert m["clipped_ratio"] == pytest.approx(0.5)


def test_measure_face_wider_than_image():
    m = measure(np.full((100, 100, 3), 100, np.uint8), FaceBox(-10, 0, 110, 100, 0.9))
    assert m["face_width_ratio"] == pytest.approx(1.2)
    assert m["clipped_ratio"] == pytest.approx(20 / 120)


def test_face_entirely_outside_image_never_passes(tmp_path):
    path = write(tmp_path, noise_image())
    r = run([FaceBox(CANVAS + 50, 0, CANVAS + 250, 200, 0.9)], path)
    assert r.gate != Gate.PASS
    valid(r)


# ── 7. lỗi hạ tầng ───────────────────────────────────────────────────────────────────────
def assert_error(result, code: ErrorCode) -> None:
    assert result.module == Module.QUALITY.value
    assert result.status == Status.ERROR and result.error_code == code
    assert not result.is_usable
    assert result.gate != Gate.PASS  # error không bao giờ là đạt
    assert result.gate is None
    assert hints(result) == []
    valid(result)


def test_no_image_no_video_is_decode_error():
    r = QualityDetector(finder=FakeFinder([box()])).predict(DetectorInput())
    assert_error(r, ErrorCode.E_DECODE)


def test_corrupt_file_is_decode_error(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"this is not an image")
    assert_error(run([box()], bad), ErrorCode.E_DECODE)


def test_nonexistent_file_is_decode_error(tmp_path):
    assert_error(run([box()], tmp_path / "nope.png"), ErrorCode.E_DECODE)


def test_finder_exception_is_internal_error(tmp_path):
    path = write(tmp_path, noise_image())
    r = QualityDetector(finder=BoomFinder()).predict(DetectorInput(images=[path]))
    assert_error(r, ErrorCode.E_INTERNAL)


def test_missing_weights_errors_and_never_uses_network(tmp_path, monkeypatch):
    def no_net(self, *args, **kwargs):
        raise AssertionError("quality không được gọi mạng")

    monkeypatch.setattr(socket.socket, "connect", no_net)
    monkeypatch.setattr(socket.socket, "connect_ex", no_net)
    empty = tmp_path / "empty-models"
    empty.mkdir()
    path = write(tmp_path, noise_image())
    r = QualityDetector(models_dir=empty).predict(DetectorInput(images=[path]))
    assert r.status == Status.ERROR
    assert not r.is_usable and r.gate != Gate.PASS
    valid(r)


def test_error_result_never_carries_pass_gate_for_any_failure(tmp_path):
    good = write(tmp_path, noise_image())
    cases = [
        QualityDetector(finder=BoomFinder()).predict(DetectorInput(images=[good])),
        QualityDetector(finder=FakeFinder([box()])).predict(DetectorInput()),
        QualityDetector(finder=FakeFinder([box()])).predict(DetectorInput(images=[tmp_path / "x"])),
    ]
    for r in cases:
        assert r.status == Status.ERROR and r.gate != Gate.PASS


# ── 8. video ─────────────────────────────────────────────────────────────────────────────
def write_video(path: Path, fourcc: str, values: list[int]) -> bool:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), 10.0, (CANVAS, CANVAS))
    if not writer.isOpened():
        return False
    for v in values:
        writer.write(np.full((CANVAS, CANVAS, 3), v, np.uint8))
    writer.release()
    capture = cv2.VideoCapture(str(path))
    try:
        ok, _ = capture.read()
    finally:
        capture.release()
    return bool(ok)


@pytest.mark.parametrize("fourcc,ext", [("mp4v", ".mp4"), ("MJPG", ".avi")])
def test_video_without_image_uses_middle_frame(tmp_path, fourcc, ext):
    values = [20, 70, 120, 170, 220]  # mỗi khung một độ chói riêng để biết khung nào được chọn
    video = tmp_path / f"clip{ext}"
    if not write_video(video, fourcc, values):
        pytest.skip(f"máy không ghi/đọc được video {fourcc}")
    finder = FakeFinder([box()])
    r = QualityDetector(finder=finder).predict(DetectorInput(video=video))
    assert r.status == Status.OK
    assert len(finder.seen) == 1
    assert float(finder.seen[0].mean()) == pytest.approx(values[len(values) // 2], abs=12)
    assert r.quality["illum"] == pytest.approx(values[2] / 255, abs=0.05)
    valid(r)


def test_image_takes_precedence_over_video(tmp_path):
    path = write(tmp_path, noise_image())
    finder = FakeFinder([box()])
    r = QualityDetector(finder=finder).predict(
        DetectorInput(images=[path], video=tmp_path / "missing.mp4")
    )
    assert r.status == Status.OK and r.gate == Gate.PASS
    assert finder.seen[0].shape[:2] == (CANVAS, CANVAS)


def test_missing_or_corrupt_video_is_decode_error(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    for video in (bad, tmp_path / "nope.mp4"):
        r = QualityDetector(finder=FakeFinder([box()])).predict(DetectorInput(video=video))
        assert_error(r, ErrorCode.E_DECODE)


# ── 9. preload ───────────────────────────────────────────────────────────────────────────
def test_preload_with_other_models_dir_requires_restart(tmp_path):
    det = QualityDetector(finder=FakeFinder([]))
    det._loaded_root = (tmp_path / "a").resolve()
    det.preload(models_dir=tmp_path / "a")  # cùng thư mục: không sao
    det.preload()  # không chỉ định: không sao
    with pytest.raises(QualityError, match="restart"):
        det.preload(models_dir=tmp_path / "b")


def test_injected_finder_version_and_preload_noop():
    det = QualityDetector(finder=FakeFinder([]))
    assert det.version == "quality-injected"
    det.preload()
    assert det.version == "quality-injected"


@pytest.fixture
def fake_scrfd(monkeypatch):
    """Giả lập trọng số SCRFD: đếm số lần nạp phiên onnxruntime thật."""
    monkeypatch.setattr(pad, "_SCRFD_SESSIONS", {})
    loads: list[Path] = []

    def fake_weights(root, model_id, filename):
        return root / model_id / filename, "0123456789abcdef"

    def fake_session(path, device=None):
        loads.append(path)
        return object()

    monkeypatch.setattr(pad, "_verified_weights", fake_weights)
    monkeypatch.setattr(pad, "_session", fake_session)
    monkeypatch.setattr(quality, "ScrfdFaceFinder", lambda session: FakeFinder([]))
    return loads


def test_preload_shares_scrfd_session_and_sets_version(tmp_path, fake_scrfd):
    first, second = QualityDetector(models_dir=tmp_path), QualityDetector(models_dir=tmp_path)
    first.preload()
    second.preload()
    assert len(fake_scrfd) == 1  # phiên dùng chung, không nạp lần hai
    assert first.version == second.version == f"{quality.QUALITY_VERSION_BASE}@01234567"


def test_preload_after_real_load_rejects_other_dir(tmp_path, fake_scrfd):
    det = QualityDetector(models_dir=tmp_path / "a")
    det.preload()
    det.preload(models_dir=tmp_path / "a")
    with pytest.raises(QualityError, match="restart"):
        det.preload(models_dir=tmp_path / "b")


def test_predict_uses_lazily_loaded_scrfd_finder(tmp_path, fake_scrfd):
    path = write(tmp_path, noise_image())
    det = QualityDetector(models_dir=tmp_path)
    r = det.predict(DetectorInput(images=[path]))
    assert len(fake_scrfd) == 1
    assert_fail(r, "FACE_CENTER", ErrorCode.E_NO_FACE)  # finder giả không thấy mặt


# ── 10. tích hợp với TrustRouter ─────────────────────────────────────────────────────────
def router_results(quality_result):
    from vericlue_ml.mock.detectors import MockDetector

    inp = DetectorInput(metadata={"scenario": "genuine"})
    values = {module: MockDetector(module).predict(inp) for module in Module}
    values[Module.QUALITY] = quality_result
    return values


def test_router_retries_with_move_closer_hint(tmp_path):
    from vericlue_ml.router.policy import TrustRouter

    r = run([box(MIN_FACE_PX - 10)], write(tmp_path, noise_image()))
    decision = TrustRouter().finalize(router_results(r))
    assert decision.status == "retry"
    assert decision.retry_hint == "MOVE_CLOSER"
    assert decision.retry_hint in RETRY_HINTS


def test_router_error_quality_goes_to_review(tmp_path):
    from vericlue_ml.router.policy import TrustRouter

    r = QualityDetector(finder=FakeFinder([box()])).predict(DetectorInput())
    assert r.status == Status.ERROR
    decision = TrustRouter().finalize(router_results(r))
    assert decision.status == "review"
    assert decision.retry_hint is None


def test_router_good_quality_does_not_block(tmp_path):
    from vericlue_ml.router.policy import TrustRouter

    r = run([box()], write(tmp_path, noise_image()))
    assert r.gate == Gate.PASS
    decision = TrustRouter().finalize(router_results(r))
    assert decision.status == "pass"
    assert decision.retry_hint is None
