"""FACE-02: FaceDeepfakeDetector (GenD) với finder/classifier giả — không cần GPU, trọng số hay mạng."""

from __future__ import annotations

import hashlib
import json
import math
import os
import socket
from pathlib import Path

import jsonschema
import numpy as np
import pytest
import yaml

from vericlue_ml.common import DetectorInput, ErrorCode, Module, Status
from vericlue_ml.face import gend, pad
from vericlue_ml.face.frames import even_indices, read_video_frames
from vericlue_ml.face.gend import (
    EKYC_FRAMES,
    FORENSIC_FRAMES,
    MIN_VALID_FRAMES,
    FaceDeepfakeDetector,
    GendError,
    align_face,
    to_tensor,
    video_scores,
)
from vericlue_ml.face.pad import FaceBox

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "packages/contracts/schemas/module_result.schema.json").read_text(encoding="utf-8")
)

cv2 = pytest.importorskip("cv2")

VIDEO_FRAMES = 45


# ── đồ giả ───────────────────────────────────────────────────────────────────────────────
def face(x: float = 40.0, y: float = 20.0, size: float = 80.0, conf: float = 0.9) -> FaceBox:
    """Mặt vuông `size` px với 5 mốc đúng bố cục chuẩn (mắt trái/phải, mũi, khóe miệng trái/phải)."""
    landmarks = tuple((x + tx * size, y + ty * size) for tx, ty in gend._ALIGN_TARGET.tolist())
    return FaceBox(x, y, x + size, y + size, conf, landmarks=landmarks)


class FakeFinder:
    """Trả `boxes` ở mỗi lần gọi; nếu có `plan` (theo thứ tự gọi) thì chỗ False trả [] (không có mặt)."""

    def __init__(self, boxes: list[FaceBox], plan: list[bool] | None = None) -> None:
        self.boxes = boxes
        self.plan = plan
        self.calls = 0
        self.markers: list[int] = []  # giá trị pixel của khung → chỉ số khung (video tổng hợp)

    def find(self, image: np.ndarray) -> list[FaceBox]:
        call = self.calls
        self.calls += 1
        self.markers.append(int(round((float(image.mean()) - 4.0) / 5.0)))
        if self.plan is not None and not self.plan[call]:
            return []
        return list(self.boxes)


class FakeClassifier:
    def __init__(self, values: list[float] | None = None, default: float = 0.5) -> None:
        self.values, self.default = values, default
        self.batches: list[np.ndarray] = []

    def p_fake(self, batch: np.ndarray) -> list[float]:
        self.batches.append(batch.copy())
        if self.values is None:
            return [self.default] * len(batch)
        return [self.values[i % len(self.values)] for i in range(len(batch))]


class BoomClassifier:
    def p_fake(self, batch: np.ndarray) -> list[float]:
        raise RuntimeError("boom")


class FixedClassifier:
    """Trả đúng danh sách `out` bất kể đầu vào (để thử NaN / sai độ dài)."""

    def __init__(self, out: list[float]) -> None:
        self.out = out

    def p_fake(self, batch: np.ndarray) -> list[float]:
        return list(self.out)


def make_images(tmp_path: Path, count: int, shape=(200, 300, 3)) -> list[Path]:
    rng = np.random.default_rng(0)
    paths = []
    for i in range(count):
        path = tmp_path / f"face{i}.png"
        assert cv2.imwrite(str(path), rng.integers(0, 255, shape, dtype=np.uint8))
        paths.append(path)
    return paths


@pytest.fixture
def image_paths(tmp_path: Path) -> list[Path]:
    return make_images(tmp_path, 4)


@pytest.fixture(scope="module")
def video_path(tmp_path_factory) -> Path:
    """Video tổng hợp 160x120, khung i toàn một mức xám 4 + 5*i (đọc ngược ra chỉ số khung)."""
    folder = tmp_path_factory.mktemp("video")
    for fourcc, name in (("MJPG", "clip.avi"), ("mp4v", "clip.mp4")):
        path = folder / name
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), 10.0, (160, 120))
        if not writer.isOpened():
            writer.release()
            continue
        for i in range(VIDEO_FRAMES):
            writer.write(np.full((120, 160, 3), 4 + 5 * i, np.uint8))
        writer.release()
        capture = cv2.VideoCapture(str(path))
        count = 0
        while capture.isOpened() and capture.grab():
            count += 1
        capture.release()
        if count == VIDEO_FRAMES:
            return path
    pytest.skip("máy này không ghi/đọc được video tổng hợp bằng cv2.VideoWriter")


def detector(boxes=None, classifier=None, plan=None, **kwargs):
    finder = FakeFinder([face()] if boxes is None else boxes, plan)
    return FaceDeepfakeDetector(finder=finder, classifier=classifier or FakeClassifier(), **kwargs)


def valid(result) -> None:
    jsonschema.validate(result.to_contract(), SCHEMA)


def evidence(result, name: str):
    return next(e for e in result.evidence if e.name == name)


@pytest.fixture(autouse=True)
def fresh_scrfd_cache(monkeypatch):
    """Cache phiên SCRFD dùng chung toàn tiến trình: mỗi test dùng cache rỗng."""
    monkeypatch.setattr(pad, "_SCRFD_SESSIONS", {})


# ── kết quả bình thường ──────────────────────────────────────────────────────────────────
def test_ok_result_shape_and_scores(image_paths):
    clf = FakeClassifier([0.1, 0.2, 0.3, 0.9])
    det = detector(classifier=clf)
    r = det.predict(DetectorInput(images=image_paths))
    assert r.status == Status.OK and r.is_usable and r.error_code is None
    assert r.module == Module.FACE_DEEPFAKE.value
    assert r.prob_attack is None  # xác suất sau hiệu chỉnh do TrustRouter tính
    assert isinstance(r.model_version, str) and r.model_version
    assert r.latency_ms >= 0

    mean, top = evidence(r, "mean").value, evidence(r, "top25_mean").value
    assert mean == pytest.approx(0.375)
    assert top == pytest.approx(0.9)  # ceil(25% × 4) = 1 khung nghi nhất
    assert r.score == pytest.approx(max(mean, top))

    series = evidence(r, "frame_scores")
    assert series.type == "timeseries"
    assert [p["frame"] for p in series.value] == [0, 1, 2, 3]
    assert [p["p_fake"] for p in series.value] == pytest.approx([0.1, 0.2, 0.3, 0.9])
    assert r.quality["frames_sampled"] == 4.0 and r.quality["frames_used"] == 4.0

    batch = clf.batches[0]
    assert batch.shape == (4, 3, 224, 224) and batch.dtype == np.float32
    valid(r)


def test_score_is_max_of_mean_and_top25(image_paths):
    r = detector(classifier=FakeClassifier(default=0.4)).predict(DetectorInput(images=image_paths))
    assert r.score == pytest.approx(0.4)
    assert evidence(r, "mean").value == pytest.approx(evidence(r, "top25_mean").value)


@pytest.mark.parametrize(
    ("values", "mean", "top"),
    [
        ([0.7], 0.7, 0.7),  # 1 khung: ít nhất 1 khung
        ([0.1, 0.2, 0.3, 0.4], 0.25, 0.4),  # ceil(1.0) = 1
        ([0.1, 0.2, 0.3, 0.4, 0.5], 0.3, 0.45),  # ceil(1.25) = 2 → (0.5 + 0.4) / 2
        ([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.5], 0.1875, 0.75),  # ceil(2.0) = 2
        ([0.2] * 8 + [0.8], 2.4 / 9, 0.4),  # 9 khung: ceil(2.25) = 3 → (0.8 + 0.2 + 0.2) / 3
    ],
)
def test_video_scores_examples(values, mean, top):
    got_mean, got_top = video_scores(values)
    assert got_mean == pytest.approx(mean)
    assert got_top == pytest.approx(top)


def test_video_scores_order_independent_and_top_ge_mean():
    values = [0.9, 0.1, 0.5, 0.3, 0.7, 0.2]
    mean, top = video_scores(values)
    assert video_scores(sorted(values)) == pytest.approx((mean, top))
    assert top >= mean  # ceil(25% × 6) = 2 → (0.9 + 0.7) / 2
    assert top == pytest.approx(0.8)


# ── không có mặt / ít mặt ────────────────────────────────────────────────────────────────
def test_no_face_in_any_frame_not_applicable(image_paths):
    clf = FakeClassifier()
    r = detector(boxes=[], classifier=clf).predict(DetectorInput(images=image_paths))
    assert r.status == Status.NOT_APPLICABLE and r.error_code == ErrorCode.E_NO_FACE
    assert not r.is_usable and r.score is None
    assert clf.batches == []  # không có crop thì không gọi mô hình
    assert r.quality["frames_sampled"] == 4.0 and r.quality["frames_used"] == 0.0
    valid(r)


@pytest.mark.parametrize(
    ("sampled", "with_face", "ok"),
    [
        (8, MIN_VALID_FRAMES, True),  # đúng ngưỡng
        (8, MIN_VALID_FRAMES - 1, False),
        (8, 8, True),
        (8, 1, False),
        (2, 2, True),  # ít khung hơn ngưỡng: cần đủ min(3, 2) = 2
        (2, 1, False),
        (1, 1, True),
    ],
)
def test_partial_faces_enough_or_degraded(tmp_path, sampled, with_face, ok):
    paths = make_images(tmp_path, sampled)
    plan = [i < with_face for i in range(sampled)]
    r = detector(plan=plan).predict(DetectorInput(images=paths))
    assert r.quality["frames_sampled"] == float(sampled)
    assert r.quality["frames_used"] == float(with_face)
    assert r.score is not None  # có điểm để xem, nhưng...
    if ok:
        assert r.status == Status.OK and r.error_code is None and r.is_usable
    else:
        assert r.status == Status.DEGRADED and r.error_code == ErrorCode.E_LOW_QUALITY
        assert not r.is_usable  # degraded không bao giờ được coi là đạt
    valid(r)


def test_partial_faces_keep_frame_indices(tmp_path):
    paths = make_images(tmp_path, 6)
    r = detector(plan=[False, True, True, False, True, True]).predict(DetectorInput(images=paths))
    assert [p["frame"] for p in evidence(r, "frame_scores").value] == [1, 2, 4, 5]


# ── chọn mặt ─────────────────────────────────────────────────────────────────────────────
def test_largest_face_is_cropped(tmp_path):
    (path,) = make_images(tmp_path, 1)
    image = cv2.imread(str(path))
    small, big = face(x=200, y=20, size=40), face(x=30, y=20, size=100)
    clf = FakeClassifier([0.3])
    r = detector(boxes=[small, big], classifier=clf).predict(DetectorInput(images=[path]))
    assert r.status == Status.OK
    expected = to_tensor(align_face(image, np.array(big.landmarks)))
    other = to_tensor(align_face(image, np.array(small.landmarks)))
    assert len(clf.batches) == 1 and len(clf.batches[0]) == 1  # đúng một crop mỗi khung
    assert np.allclose(clf.batches[0][0], expected)
    assert not np.allclose(clf.batches[0][0], other)


def test_faces_without_landmarks_or_tiny_are_ignored(tmp_path):
    (path,) = make_images(tmp_path, 1)
    image = cv2.imread(str(path))
    good = face(x=30, y=20, size=60)
    huge_no_landmarks = FaceBox(0, 0, 190, 190, 0.99, landmarks=None)
    tiny = FaceBox(5, 5, 6, 6, 0.99, landmarks=good.landmarks)  # cạnh < 2 px
    clf = FakeClassifier([0.3])
    r = detector(boxes=[huge_no_landmarks, tiny, good], classifier=clf).predict(
        DetectorInput(images=[path])
    )
    assert r.status == Status.OK
    assert np.allclose(clf.batches[0][0], to_tensor(align_face(image, np.array(good.landmarks))))


def test_degenerate_landmarks_skip_frame(image_paths):
    collapsed = FaceBox(10, 10, 90, 90, 0.9, landmarks=((50.0, 50.0),) * 5)
    clf = FakeClassifier()
    r = detector(boxes=[collapsed], classifier=clf).predict(DetectorInput(images=image_paths))
    assert r.status == Status.NOT_APPLICABLE and r.error_code == ErrorCode.E_NO_FACE
    assert clf.batches == []


# ── số khung & chỉ số khung ──────────────────────────────────────────────────────────────
def test_even_indices_properties():
    assert even_indices(0, 8) == [] and even_indices(10, 0) == []
    assert even_indices(5, 8) == [0, 1, 2, 3, 4]  # ít khung hơn yêu cầu: lấy hết
    assert even_indices(1, 1) == [0]
    got = even_indices(VIDEO_FRAMES, 8)
    assert len(got) == 8 and got[0] == 0 and got[-1] == VIDEO_FRAMES - 1
    gaps = np.diff(got)
    assert gaps.min() >= 1 and gaps.max() - gaps.min() <= 1  # đều nhau (±1)
    assert even_indices(VIDEO_FRAMES, 1) == [0]


def test_ekyc_samples_eight_frames_from_video(video_path):
    det = detector()
    r = det.predict(DetectorInput(video=video_path))
    assert r.status == Status.OK
    expected = even_indices(VIDEO_FRAMES, EKYC_FRAMES)
    assert len(expected) == EKYC_FRAMES == 8
    assert r.quality["frames_sampled"] == 8.0 and r.quality["frames_used"] == 8.0
    assert [p["frame"] for p in evidence(r, "frame_scores").value] == expected
    # khung thật được giải mã (không chỉ là chỉ số): dấu pixel khớp, gồm khung đầu và khung cuối
    assert det._finder.markers == expected
    assert det._finder.markers[0] == 0 and det._finder.markers[-1] == VIDEO_FRAMES - 1
    valid(r)


def test_forensic_mode_samples_thirty_two_frames(video_path):
    det = detector()
    r = det.predict(DetectorInput(video=video_path, metadata={"mode": "forensic"}))
    assert r.status == Status.OK
    expected = even_indices(VIDEO_FRAMES, FORENSIC_FRAMES)
    assert len(expected) == FORENSIC_FRAMES == 32
    assert r.quality["frames_sampled"] == 32.0
    assert det._finder.markers == expected
    assert expected[0] == 0 and expected[-1] == VIDEO_FRAMES - 1
    valid(r)


def test_other_mode_is_ekyc_and_num_frames_override(video_path):
    r = detector().predict(DetectorInput(video=video_path, metadata={"mode": "ekyc"}))
    assert r.quality["frames_sampled"] == float(EKYC_FRAMES)
    r = detector(num_frames=5).predict(DetectorInput(video=video_path))
    assert r.quality["frames_sampled"] == 5.0


def test_read_video_frames_returns_decoded_bgr_frames(video_path):
    frames = read_video_frames(video_path, 4)
    assert [i for i, _ in frames] == even_indices(VIDEO_FRAMES, 4)
    for index, image in frames:
        assert image.shape == (120, 160, 3)
        assert abs(float(image.mean()) - (4 + 5 * index)) < 3


def test_fewer_images_than_requested_uses_all(tmp_path):
    paths = make_images(tmp_path, 5)
    r = detector().predict(DetectorInput(images=paths))
    assert r.quality["frames_sampled"] == 5.0


def test_many_images_are_sampled_evenly(tmp_path):
    paths = make_images(tmp_path, 20, shape=(60, 80, 3))
    det = detector(boxes=[face(x=10, y=5, size=40)])
    r = det.predict(DetectorInput(images=paths))
    assert [p["frame"] for p in evidence(r, "frame_scores").value] == even_indices(20, 8)


# ── video hay ảnh ────────────────────────────────────────────────────────────────────────
def test_video_takes_precedence_over_images(video_path, tmp_path):
    missing = [tmp_path / "does-not-exist.png"]  # nếu dùng ảnh thì sẽ ra E_DECODE
    r = detector().predict(DetectorInput(video=video_path, images=missing))
    assert r.status == Status.OK
    assert r.quality["frames_sampled"] == float(EKYC_FRAMES)


def test_images_used_when_no_video(image_paths):
    r = detector().predict(DetectorInput(images=image_paths))
    assert r.status == Status.OK and r.quality["frames_sampled"] == 4.0


# ── lỗi ──────────────────────────────────────────────────────────────────────────────────
def test_no_video_and_no_images_is_decode_error():
    r = detector().predict(DetectorInput())
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE
    assert not r.is_usable
    valid(r)


@pytest.mark.parametrize("suffix", [".webm", ".mp4"])
def test_corrupt_video_is_decode_error(tmp_path, suffix):
    bad = tmp_path / f"bad{suffix}"
    bad.write_bytes(b"this is definitely not a video" * 50)
    r = detector().predict(DetectorInput(video=bad))
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE
    valid(r)


def test_nonexistent_video_is_decode_error(tmp_path):
    r = detector().predict(DetectorInput(video=tmp_path / "nope.mp4"))
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE


def test_corrupt_image_is_decode_error(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"this is not an image")
    r = detector().predict(DetectorInput(images=[bad]))
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE
    valid(r)


def test_one_corrupt_image_among_good_is_decode_error(tmp_path):
    good = make_images(tmp_path, 2)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    r = detector().predict(DetectorInput(images=[good[0], bad, good[1]]))
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE


def test_nonexistent_image_is_decode_error(tmp_path):
    r = detector().predict(DetectorInput(images=[tmp_path / "nope.png"]))
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE


def test_classifier_exception_is_internal_error(image_paths):
    r = detector(classifier=BoomClassifier()).predict(DetectorInput(images=image_paths))
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_INTERNAL
    assert not r.is_usable and r.score is None
    valid(r)


@pytest.mark.parametrize(
    "out",
    [[math.nan] * 4, [0.1, math.inf, 0.1, 0.1], [0.1, 0.2], []],
    ids=["nan", "inf", "wrong-length", "empty"],
)
def test_invalid_classifier_scores_are_error(image_paths, out):
    r = detector(classifier=FixedClassifier(out)).predict(DetectorInput(images=image_paths))
    assert r.status == Status.ERROR and not r.is_usable
    assert r.score is None
    valid(r)


# ── trọng số ─────────────────────────────────────────────────────────────────────────────
PAYLOADS = {
    ("scrfd-10g", "det_10g.onnx"): b"fake-scrfd",
    ("clip-vit-large-patch14", "config.json"): b"fake-clip-config",
    ("clip-vit-large-patch14", "preprocessor_config.json"): b"fake-clip-pre",
    ("gend-clip-l14", "config.json"): b"fake-gend-config",
    ("gend-clip-l14", "model.safetensors"): b"fake-gend-weights",
}


@pytest.fixture
def fake_models(tmp_path, monkeypatch):
    """Manifest giả cho 5 file mà GenD cần; trả (thư mục models rỗng, hàm ghi file đúng nội dung)."""
    by_model: dict[str, list[dict]] = {}
    for (model_id, name), payload in PAYLOADS.items():
        by_model.setdefault(model_id, []).append(
            {"path": name, "sha256": hashlib.sha256(payload).hexdigest()}
        )
    manifest = {
        "models": [
            {"id": mid, "source": {"revision": f"rev-{mid}"}, "files": files}
            for mid, files in by_model.items()
        ]
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(manifest_path))
    root = tmp_path / "models"
    root.mkdir()

    def write(model_id: str, name: str, payload: bytes | None = None) -> None:
        (root / model_id).mkdir(exist_ok=True)
        (root / model_id / name).write_bytes(
            PAYLOADS[(model_id, name)] if payload is None else payload
        )

    return root, write


def _predict_with_root(root: Path, image: Path):
    return FaceDeepfakeDetector(models_dir=root).predict(DetectorInput(images=[image]))


def test_missing_detector_weights_is_error(fake_models, image_paths):
    root, _ = fake_models
    r = _predict_with_root(root, image_paths[0])
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_INTERNAL
    assert not r.is_usable
    valid(r)


def test_wrong_sha_detector_weights_is_integrity_error(fake_models, image_paths):
    root, write = fake_models
    write("scrfd-10g", "det_10g.onnx", b"tampered")
    r = _predict_with_root(root, image_paths[0])
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_INTEGRITY
    valid(r)


@pytest.fixture
def past_detector(monkeypatch):
    """Bỏ qua bước SCRFD để test tới được kiểm tra trọng số gend/clip (cần torch + transformers)."""
    pytest.importorskip("torch")
    pytest.importorskip("safetensors")
    pytest.importorskip("transformers")
    monkeypatch.setattr(gend, "shared_scrfd_session", lambda root, device=None: (object(), "rev"))


@pytest.mark.parametrize(
    ("model_id", "name"), [k for k in PAYLOADS if k[0] != "scrfd-10g"], ids=lambda v: str(v)
)
def test_missing_gend_or_clip_file_is_error(
    fake_models, past_detector, image_paths, model_id, name
):
    root, write = fake_models
    for key in PAYLOADS:
        if key != (model_id, name) and key[0] != "scrfd-10g":
            write(*key)
    r = _predict_with_root(root, image_paths[0])
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_INTERNAL
    assert not r.is_usable


@pytest.mark.parametrize(
    ("model_id", "name"), [k for k in PAYLOADS if k[0] != "scrfd-10g"], ids=lambda v: str(v)
)
def test_wrong_sha_gend_or_clip_file_is_integrity_error(
    fake_models, past_detector, image_paths, model_id, name
):
    root, write = fake_models
    for key in PAYLOADS:
        if key[0] != "scrfd-10g":
            write(*key, b"tampered" if key == (model_id, name) else None)
    r = _predict_with_root(root, image_paths[0])
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_INTEGRITY
    valid(r)


def test_predict_without_weights_errors_and_never_uses_network(
    fake_models, monkeypatch, image_paths
):
    def no_net(self, *args, **kwargs):
        raise AssertionError("GenD không được gọi mạng")

    monkeypatch.setattr(socket.socket, "connect", no_net)
    monkeypatch.setattr(socket.socket, "connect_ex", no_net)
    root, _ = fake_models  # thư mục rỗng
    r = _predict_with_root(root, image_paths[0])
    assert r.status == Status.ERROR
    assert not r.is_usable
    valid(r)


# ── tiền xử lý ───────────────────────────────────────────────────────────────────────────
def test_to_tensor_shape_dtype_and_normalisation():
    bgr = np.zeros((50, 60, 3), np.uint8)
    bgr[..., 0], bgr[..., 1], bgr[..., 2] = 10, 100, 200  # B, G, R
    out = to_tensor(bgr)
    assert out.shape == (3, 224, 224) and out.dtype == np.float32
    assert out.flags["C_CONTIGUOUS"]
    # kênh 0 = R = 200, kênh 1 = G = 100, kênh 2 = B = 10 (BGR → RGB)
    for channel, value in enumerate((200, 100, 10)):
        expected = (value / 255.0 - gend.CLIP_MEAN[channel]) / gend.CLIP_STD[channel]
        assert np.allclose(out[channel], expected, atol=1e-4)


def test_to_tensor_white_and_black_extremes():
    white = to_tensor(np.full((224, 224, 3), 255, np.uint8))
    black = to_tensor(np.zeros((224, 224, 3), np.uint8))
    for channel in range(3):
        assert np.allclose(
            white[channel], (1 - gend.CLIP_MEAN[channel]) / gend.CLIP_STD[channel], atol=1e-4
        )
        assert np.allclose(
            black[channel], -gend.CLIP_MEAN[channel] / gend.CLIP_STD[channel], atol=1e-4
        )


def _gradient(height: int, width: int) -> np.ndarray:
    ys, xs = np.mgrid[0:height, 0:width]
    return np.stack([xs, ys, (xs + ys) // 2], axis=-1).astype(np.uint8)


def test_align_face_square_output_scales_with_face():
    image = _gradient(300, 300)
    base = gend._ALIGN_TARGET
    for size in (50.0, 100.0):
        out = align_face(image, base * size + 40.0)
        side = round(size * gend.ALIGN_SCALE)
        assert out.shape == (side, side, 3) and out.dtype == np.uint8
        assert out.std() > 0  # không suy biến thành ảnh phẳng


def test_align_face_identity_when_landmarks_on_target():
    # mốc = đích chuẩn hóa → phép biến đổi là phép đồng nhất, ảnh ra = góc trên-trái của ảnh vào
    image = _gradient(200, 200)
    landmarks = gend._ALIGN_TARGET * 100.0 + 15.0
    out = align_face(image, landmarks)
    assert out.shape == (130, 130, 3)
    diff = np.abs(out.astype(int) - image[:130, :130].astype(int))
    assert diff.max() <= 2


def test_align_face_degenerate_landmarks_raise():
    with pytest.raises(GendError) as err:
        align_face(_gradient(100, 100), np.full((5, 2), 50.0, np.float32))
    assert err.value.code == ErrorCode.E_NO_FACE


# ── preload ──────────────────────────────────────────────────────────────────────────────
def test_preload_with_other_models_dir_requires_restart(tmp_path):
    det = detector()
    det._loaded_root = (tmp_path / "a").resolve()
    det.preload(models_dir=tmp_path / "a")  # cùng thư mục: không sao
    det.preload()  # không chỉ định: không sao
    with pytest.raises(GendError, match="restart"):
        det.preload(models_dir=tmp_path / "b")


def test_preload_injected_without_loaded_root_is_noop(tmp_path):
    detector().preload(models_dir=tmp_path / "anywhere")  # chưa nạp thật → không ném


# ── GendClassifier (torch giả nhỏ) ───────────────────────────────────────────────────────
def test_gend_classifier_softmax_label_one_and_batching():
    torch = pytest.importorskip("torch")

    class Out:
        def __init__(self, pooler_output):
            self.pooler_output = pooler_output

    class FakeVision:
        def __init__(self):
            self.batch_sizes: list[int] = []

        def __call__(self, pixel_values):
            self.batch_sizes.append(len(pixel_values))
            level = pixel_values.mean(dim=(1, 2, 3))
            return Out(torch.stack([level, torch.ones_like(level)], dim=1))

    n = 20
    assert n > 2 * gend.BATCH_SIZE
    levels = np.random.default_rng(7).permutation(n).astype(np.float32) / 10.0 - 1.0
    batch = np.broadcast_to(levels[:, None, None, None], (n, 3, 8, 8)).astype(np.float32).copy()

    weight = torch.tensor([[0.0, 0.0], [3.0, 0.0]])  # logit giả = 3 · x/√(x²+1) + bias[1]
    bias = torch.tensor([0.0, 0.3])
    vision = FakeVision()
    clf = gend.GendClassifier(vision, weight, bias, "cpu")
    out = clf.p_fake(batch)

    assert vision.batch_sizes == [8, 8, 4]
    assert len(out) == n and all(isinstance(v, float) for v in out)
    unit = levels / np.sqrt(levels**2 + 1.0)
    expected = 1.0 / (1.0 + np.exp(-(3.0 * unit + 0.3)))  # softmax([0, z])[1] = sigmoid(z)
    assert out == pytest.approx(expected.tolist(), abs=1e-5)
    assert all(0.0 <= v <= 1.0 for v in out)


# ── thật (cần trọng số) ──────────────────────────────────────────────────────────────────
@pytest.mark.slow
def test_real_weights_never_error_on_faceless_image(tmp_path):
    pytest.importorskip("onnxruntime")
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    if not os.environ.get("MODELS_DIR"):
        pytest.skip("đặt MODELS_DIR để chạy test với trọng số thật")
    models = Path(os.environ["MODELS_DIR"])
    needed = [models / "scrfd-10g" / "det_10g.onnx"] + [
        models / mid / name for (mid, name) in PAYLOADS if mid != "scrfd-10g"
    ]
    if not all(p.is_file() for p in needed):
        pytest.skip("thiếu trọng số scrfd-10g / clip-vit-large-patch14 / gend-clip-l14")
    path = tmp_path / "noise.png"
    noise = np.random.default_rng(3).integers(0, 255, (480, 640, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), noise)
    result = FaceDeepfakeDetector(models).predict(DetectorInput(images=[path]))
    assert result.status in {Status.OK, Status.NOT_APPLICABLE, Status.DEGRADED}
    valid(result)
