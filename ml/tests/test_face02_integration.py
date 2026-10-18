"""FACE-02: SCRFD (5 mốc, tham số tiền xử lý), phiên dùng chung, khung thiếu và fail-closed với router.

Dùng phiên onnxruntime giả có đầu ra dựng sẵn — không cần trọng số hay GPU.
"""

from __future__ import annotations

import numpy as np
import pytest

from vericlue_ml.common import DetectorInput, ErrorCode, Module, Status
from vericlue_ml.face import gend, pad
from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.face.pad import FaceBox, ScrfdFaceFinder

SIZE = 640
CELL_X, CELL_Y = 20, 30  # ô stride-8 chứa mặt giả
ANCHOR = (CELL_Y * (SIZE // 8) + CELL_X) * 2  # 2 anchor mỗi ô; lấy anchor đầu


class _Meta:
    def __init__(self, name: str, shape=None) -> None:
        self.name, self.shape = name, shape


class FakeScrfdSession:
    """Một mặt tại ô (20, 30) tầng stride 8: hộp ±40 px quanh (160, 240), 5 mốc cố định."""

    def __init__(self) -> None:
        self.fed: list[np.ndarray] = []

    def get_inputs(self):
        return [_Meta("input.1", [1, 3, SIZE, SIZE])]

    def get_outputs(self):
        return [_Meta(f"out{i}") for i in range(9)]

    def run(self, names, feed):
        self.fed.append(next(iter(feed.values())))
        cells = [(SIZE // s) ** 2 * 2 for s in (8, 16, 32)]
        scores = [np.zeros((n, 1), np.float32) for n in cells]
        boxes = [np.zeros((n, 4), np.float32) for n in cells]
        points = [np.zeros((n, 10), np.float32) for n in cells]
        scores[0][ANCHOR] = 0.99
        boxes[0][ANCHOR] = [5, 5, 5, 5]  # × stride 8 = 40 px
        points[0][ANCHOR] = [-2, -1, 2, -1, 0, 0, -1, 2, 1, 2]
        return scores + boxes + points


def solid(b: int, g: int, r: int) -> np.ndarray:
    image = np.empty((SIZE, SIZE, 3), np.uint8)
    image[:] = (b, g, r)
    return image


def test_scrfd_decodes_box_and_five_landmarks_in_order():
    [face] = ScrfdFaceFinder(FakeScrfdSession()).find(solid(10, 20, 30))
    assert (face.x1, face.y1, face.x2, face.y2) == (120.0, 200.0, 200.0, 280.0)
    # (mắt trái, mắt phải, mũi, khóe miệng trái, khóe miệng phải) = tâm (160, 240) + offset × 8
    assert face.landmarks == (
        (144.0, 232.0),
        (176.0, 232.0),
        (160.0, 240.0),
        (152.0, 256.0),
        (168.0, 256.0),
    )


def test_scrfd_landmarks_are_scaled_back_to_the_original_image():
    big = np.zeros((SIZE * 2, SIZE * 2, 3), np.uint8)  # letterbox co 0,5 → mọi toạ độ nhân đôi
    [face] = ScrfdFaceFinder(FakeScrfdSession()).find(big)
    assert (face.x1, face.y1) == (240.0, 400.0)
    assert face.landmarks[2] == (320.0, 480.0)


def test_scrfd_default_preprocessing_is_unchanged_for_face_pad():
    """FACE-01: chia 127,5 và giữ thứ tự kênh BGR."""
    session = FakeScrfdSession()
    ScrfdFaceFinder(session).find(solid(10, 20, 30))
    tensor = session.fed[0]
    assert tensor.shape == (1, 3, SIZE, SIZE)
    assert tensor[0, 0, 0, 0] == pytest.approx((10 - 127.5) / 127.5)  # kênh 0 = B
    assert tensor[0, 2, 0, 0] == pytest.approx((30 - 127.5) / 127.5)  # kênh 2 = R


def test_scrfd_gend_preprocessing_divides_by_128_and_swaps_to_rgb():
    """GenD (src/retinaface.py): blobFromImage(1/128, mean 127,5, swapRB=True)."""
    session = FakeScrfdSession()
    ScrfdFaceFinder(session, scale=gend.SCRFD_SCALE, swap_rb=True).find(solid(10, 20, 30))
    tensor = session.fed[0]
    assert tensor[0, 0, 0, 0] == pytest.approx((30 - 127.5) / 128.0)  # kênh 0 = R
    assert tensor[0, 2, 0, 0] == pytest.approx((10 - 127.5) / 128.0)  # kênh 2 = B


# ── phiên SCRFD dùng chung ───────────────────────────────────────────────────────────────
@pytest.fixture
def counted_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr(pad, "_SCRFD_SESSIONS", {})
    calls = {"verify": 0, "session": 0}

    def verified(root, model_id, filename):
        calls["verify"] += 1
        return root / filename, "abcdef1234567890"

    def session(path, device=None):
        calls["session"] += 1
        return object()

    monkeypatch.setattr(pad, "_verified_weights", verified)
    monkeypatch.setattr(pad, "_session", session)
    return calls, tmp_path


def test_shared_scrfd_session_is_built_once_per_root_and_device(counted_sessions):
    calls, root = counted_sessions
    first = pad.shared_scrfd_session(root, "cpu")
    again = pad.shared_scrfd_session(root, "cpu")
    assert first is again
    assert first[1] == "abcdef1234567890"
    assert calls == {"verify": 1, "session": 1}
    pad.shared_scrfd_session(root / "other", "cpu")
    pad.shared_scrfd_session(root, "cuda")
    assert calls == {"verify": 3, "session": 3}


def test_shared_scrfd_session_failure_is_not_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(pad, "_SCRFD_SESSIONS", {})
    attempts = []

    def verified(root, model_id, filename):
        attempts.append(1)
        raise pad.PadError("Thiếu trọng số", ErrorCode.E_INTEGRITY)

    monkeypatch.setattr(pad, "_verified_weights", verified)
    for _ in range(2):
        with pytest.raises(pad.PadError):
            pad.shared_scrfd_session(tmp_path, "cpu")
    assert len(attempts) == 2


# ── khung thiếu không được thành "đủ" ────────────────────────────────────────────────────
class FixedFinder:
    def find(self, image):
        return [
            FaceBox(
                10,
                10,
                110,
                110,
                0.99,
                landmarks=((35, 45), (85, 45), (60, 60), (42, 85), (78, 85)),
            )
        ]


class ConstClassifier:
    def p_fake(self, batch):
        return [0.9] * len(batch)


def frames_iter(count: int):
    for index in range(count):
        yield index, np.full((120, 120, 3), 90, np.uint8)


def test_video_that_decodes_only_one_of_eight_frames_is_degraded(monkeypatch):
    """Video cắt cụt: 1/8 khung giải mã được → degraded, không phải ok từ một khung."""
    monkeypatch.setattr(gend, "sample_video", lambda path, count: (8, frames_iter(1)))
    detector = FaceDeepfakeDetector(finder=FixedFinder(), classifier=ConstClassifier())
    result = detector.predict(DetectorInput(video="clip.webm"))
    assert result.status == Status.DEGRADED
    assert result.error_code == ErrorCode.E_LOW_QUALITY
    assert result.quality["frames_sampled"] == 8.0
    assert result.quality["frames_used"] == 1.0
    assert not result.is_usable


def test_video_with_enough_decoded_frames_is_ok(monkeypatch):
    monkeypatch.setattr(gend, "sample_video", lambda path, count: (8, frames_iter(8)))
    detector = FaceDeepfakeDetector(finder=FixedFinder(), classifier=ConstClassifier())
    result = detector.predict(DetectorInput(video="clip.webm"))
    assert result.status == Status.OK
    assert result.quality["frames_used"] == 8.0


# ── fail-closed với router ───────────────────────────────────────────────────────────────
def router_results(face_deepfake):
    from vericlue_ml.mock.detectors import MockDetector

    values = {
        module: MockDetector(module).predict(DetectorInput(metadata={"scenario": "genuine"}))
        for module in Module
    }
    values[Module.FACE_DEEPFAKE] = face_deepfake
    return values


class NoFaceFinder:
    def find(self, image):
        return []


class BoomClassifier:
    def p_fake(self, batch):
        raise RuntimeError("boom")


@pytest.mark.parametrize(
    ("finder", "classifier", "status"),
    [
        (NoFaceFinder(), ConstClassifier(), Status.NOT_APPLICABLE),
        (FixedFinder(), BoomClassifier(), Status.ERROR),
    ],
)
def test_router_never_passes_when_face_deepfake_is_not_ok(monkeypatch, finder, classifier, status):
    from vericlue_ml.router.policy import TrustRouter

    monkeypatch.setattr(gend, "sample_video", lambda path, count: (8, frames_iter(8)))
    result = FaceDeepfakeDetector(finder=finder, classifier=classifier).predict(
        DetectorInput(video="clip.webm")
    )
    assert result.status == status
    assert TrustRouter().finalize(router_results(result)).status == "review"


def test_router_never_passes_when_face_deepfake_is_degraded(monkeypatch):
    from vericlue_ml.router.policy import TrustRouter

    monkeypatch.setattr(gend, "sample_video", lambda path, count: (8, frames_iter(1)))
    result = FaceDeepfakeDetector(finder=FixedFinder(), classifier=ConstClassifier()).predict(
        DetectorInput(video="clip.webm")
    )
    assert result.status == Status.DEGRADED
    assert TrustRouter().finalize(router_results(result)).status == "review"


def test_router_does_not_pass_uncalibrated_real_face_deepfake_score(monkeypatch):
    """Điểm thô (prob_attack trống, chưa có calibrator) không bao giờ đủ để pass."""
    from vericlue_ml.router.policy import TrustRouter

    monkeypatch.setattr(gend, "sample_video", lambda path, count: (8, frames_iter(8)))
    result = FaceDeepfakeDetector(finder=FixedFinder(), classifier=ConstClassifier()).predict(
        DetectorInput(video="clip.webm")
    )
    assert result.status == Status.OK
    assert result.prob_attack is None
    assert TrustRouter().finalize(router_results(result)).status == "review"


# ── model_version, luồng CPU, mở video lỗi ───────────────────────────────────────────────
def test_model_version_names_all_revisions_and_the_aggregation(monkeypatch, tmp_path):
    monkeypatch.setattr(
        gend, "shared_scrfd_session", lambda root, device=None: (FakeScrfdSession(), "bfcc7d48ea84")
    )
    monkeypatch.setattr(
        gend,
        "_load_classifier",
        lambda root, device: (ConstClassifier(), "891ce014a030", "32bd64288804"),
    )
    detector = FaceDeepfakeDetector(models_dir=tmp_path)
    detector.preload(device="cpu")
    assert detector.version == (
        "gend-clip-l14@891ce014+clip@32bd6428+scrfd-10g@bfcc7d48+agg-maxmeantop25-v1"
    )


def test_injected_version_still_carries_the_aggregation_tag():
    version = FaceDeepfakeDetector(finder=FixedFinder(), classifier=ConstClassifier()).version
    assert version.endswith("+" + gend.AGGREGATION_TAG)


def test_unopenable_video_is_a_decode_error_not_no_face(tmp_path):
    result = FaceDeepfakeDetector(finder=FixedFinder(), classifier=ConstClassifier()).predict(
        DetectorInput(video=tmp_path / "missing.webm")
    )
    assert result.status == Status.ERROR
    assert result.error_code == ErrorCode.E_DECODE


def test_video_that_cannot_be_reopened_for_sampling_is_a_decode_error(monkeypatch, tmp_path):
    """Lượt đếm khung mở được nhưng lượt đọc lại thì không → E_DECODE (không phải E_NO_FACE)."""
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 64))
    if not writer.isOpened():
        pytest.skip("không ghi được video thử")
    for _ in range(12):
        writer.write(np.full((64, 64, 3), 100, np.uint8))
    writer.release()

    real = cv2.VideoCapture
    opened = []

    def flaky(*args):
        opened.append(1)
        if len(opened) == 1:
            return real(*args)

        class Closed:
            def isOpened(self):
                return False

            def release(self):
                pass

        return Closed()

    monkeypatch.setattr(cv2, "VideoCapture", flaky)
    result = FaceDeepfakeDetector(finder=FixedFinder(), classifier=ConstClassifier()).predict(
        DetectorInput(video=path)
    )
    assert result.status == Status.ERROR
    assert result.error_code == ErrorCode.E_DECODE


def test_cpu_limits_torch_threads_and_gpu_does_not(monkeypatch):
    torch = pytest.importorskip("torch")
    seen = []
    monkeypatch.setattr(torch, "set_num_threads", lambda n: seen.append(n))
    monkeypatch.setattr("os.cpu_count", lambda: 16)
    gend._limit_cpu_threads("cuda")
    assert seen == []
    gend._limit_cpu_threads("cpu")
    assert seen == [gend.GEND_CPU_THREADS]
    monkeypatch.setattr("os.cpu_count", lambda: 2)
    gend._limit_cpu_threads("cpu")
    assert seen[-1] == 2
