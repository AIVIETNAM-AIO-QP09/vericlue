"""FACE-01: FacePadDetector với finder/classifier giả — không cần GPU, trọng số hay mạng."""

from __future__ import annotations

import hashlib
import json
import os
import socket
from pathlib import Path

import jsonschema
import numpy as np
import pytest
import yaml

from vericlue_ml.common import DetectorInput, ErrorCode, Module, Status
from vericlue_ml.face import pad
from vericlue_ml.face.pad import FaceBox, FacePadDetector, PadError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "packages/contracts/schemas/module_result.schema.json").read_text(encoding="utf-8")
)

cv2 = pytest.importorskip("cv2")


class FakeFinder:
    def __init__(self, boxes: list[FaceBox]) -> None:
        self.boxes = boxes

    def find(self, image: np.ndarray) -> list[FaceBox]:
        return list(self.boxes)


class FakeClassifier:
    def __init__(self, p_real: float = 0.8) -> None:
        self.value = p_real
        self.boxes: list[FaceBox] = []

    def p_real(self, image: np.ndarray, box: FaceBox) -> float:
        self.boxes.append(box)
        return self.value


class BoomClassifier:
    def p_real(self, image: np.ndarray, box: FaceBox) -> float:
        raise RuntimeError("boom")


def box(size: float, x: float = 10.0, conf: float = 0.9) -> FaceBox:
    return FaceBox(x, 10.0, x + size, 10.0 + size, conf)


@pytest.fixture
def image_path(tmp_path: Path) -> Path:
    path = tmp_path / "face.png"
    rng = np.random.default_rng(0)
    assert cv2.imwrite(str(path), rng.integers(0, 255, (200, 300, 3), dtype=np.uint8))
    return path


def detector(boxes, classifier=None):
    return FacePadDetector(finder=FakeFinder(boxes), classifier=classifier or FakeClassifier())


def run(det, path):
    return det.predict(DetectorInput(images=[path]))


def valid(result) -> None:
    jsonschema.validate(result.to_contract(), SCHEMA)


def test_one_face_ok(image_path):
    r = run(detector([box(100)], FakeClassifier(0.8)), image_path)
    assert r.status == Status.OK and r.is_usable
    assert r.module == Module.FACE_PAD.value
    assert r.prob_attack == pytest.approx(0.2)
    assert 0.0 <= r.score <= 1.0
    assert isinstance(r.model_version, str) and r.model_version
    assert r.latency_ms >= 0
    valid(r)


def test_prob_attack_is_one_minus_p_real(image_path):
    r = run(detector([box(100)], FakeClassifier(0.05)), image_path)
    assert r.prob_attack == pytest.approx(0.95)


def test_no_face_not_applicable(image_path):
    r = run(detector([]), image_path)
    assert r.status == Status.NOT_APPLICABLE
    assert r.error_code == ErrorCode.E_NO_FACE
    assert not r.is_usable
    valid(r)


def test_two_faces_at_exact_ratio_degraded(image_path):
    # diện tích mặt hai = đúng 0,5 × mặt một → degraded
    r = run(detector([box(100), box(100 * 0.5**0.5, x=150)]), image_path)
    assert r.status == Status.DEGRADED
    assert r.error_code == ErrorCode.E_MULTI_FACE
    assert not r.is_usable
    valid(r)


def test_two_equal_faces_degraded(image_path):
    r = run(detector([box(80), box(80, x=150)]), image_path)
    assert r.status == Status.DEGRADED and r.error_code == ErrorCode.E_MULTI_FACE


def test_much_smaller_second_face_uses_largest(image_path):
    clf = FakeClassifier(0.9)
    big = box(100)
    r = run(detector([box(40, x=200), big], clf), image_path)  # 1600/10000 < 0.5
    assert r.status == Status.OK
    assert clf.boxes == [big]
    valid(r)


def test_missing_image_is_decode_error():
    det = FacePadDetector(finder=FakeFinder([box(50)]), classifier=FakeClassifier())
    r = det.predict(DetectorInput())
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE
    assert not r.is_usable
    valid(r)


def test_corrupt_file_is_decode_error(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"this is not an image")
    r = run(detector([box(50)]), bad)
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE


def test_nonexistent_file_is_decode_error(tmp_path):
    r = run(detector([box(50)]), tmp_path / "nope.png")
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_DECODE


def test_classifier_exception_is_internal_error(image_path):
    r = run(detector([box(50)], BoomClassifier()), image_path)
    assert r.status == Status.ERROR and r.error_code == ErrorCode.E_INTERNAL
    assert not r.is_usable
    valid(r)


# ── trọng số ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def fake_models(tmp_path, monkeypatch):
    payload = b"fake-onnx-bytes"
    manifest = {
        "models": [
            {
                "id": "m1",
                "source": {"revision": "abcdef0123456789"},
                "files": [{"path": "w.onnx", "sha256": hashlib.sha256(payload).hexdigest()}],
            }
        ]
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    monkeypatch.setenv("ML_MODELS_MANIFEST", str(manifest_path))
    root = tmp_path / "models"
    root.mkdir()
    return root, payload


def test_weights_missing_file(fake_models):
    root, _ = fake_models
    with pytest.raises(PadError) as err:
        pad._verified_weights(root, "m1", "w.onnx")
    assert err.value.code == ErrorCode.E_INTERNAL


def test_weights_wrong_sha(fake_models):
    root, _ = fake_models
    (root / "m1").mkdir()
    (root / "m1" / "w.onnx").write_bytes(b"tampered")
    with pytest.raises(PadError) as err:
        pad._verified_weights(root, "m1", "w.onnx")
    assert err.value.code == ErrorCode.E_INTEGRITY


def test_weights_ok(fake_models):
    root, payload = fake_models
    (root / "m1").mkdir()
    (root / "m1" / "w.onnx").write_bytes(payload)
    path, revision = pad._verified_weights(root, "m1", "w.onnx")
    assert path == root / "m1" / "w.onnx" and revision == "abcdef0123456789"


def test_weights_unknown_model_in_manifest(fake_models):
    root, _ = fake_models
    with pytest.raises(PadError):
        pad._verified_weights(root, "other", "w.onnx")


def test_predict_without_weights_errors_and_never_uses_network(tmp_path, monkeypatch, image_path):
    def no_net(self, *args, **kwargs):
        raise AssertionError("PAD không được gọi mạng")

    monkeypatch.setattr(socket.socket, "connect", no_net)
    monkeypatch.setattr(socket.socket, "connect_ex", no_net)
    empty = tmp_path / "empty-models"
    empty.mkdir()
    r = FacePadDetector(models_dir=empty).predict(DetectorInput(images=[image_path]))
    assert r.status == Status.ERROR
    assert not r.is_usable
    valid(r)


# ── hàm nhỏ ──────────────────────────────────────────────────────────────────────────────
def test_letterbox_landscape_and_portrait():
    canvas, factor = pad._letterbox(np.full((100, 200, 3), 255, np.uint8), 640)
    assert canvas.shape == (640, 640, 3) and canvas.dtype == np.uint8
    assert factor == pytest.approx(3.2)
    assert canvas[:320, :640].min() == 255 and canvas[320:].max() == 0
    canvas, factor = pad._letterbox(np.full((200, 100, 3), 255, np.uint8), 640)
    assert canvas.shape == (640, 640, 3) and factor == pytest.approx(3.2)
    assert canvas[:, 320:].max() == 0


def test_nms_suppresses_overlap_keeps_best():
    dets = np.array(
        [[0, 0, 100, 100, 0.9], [2, 2, 102, 102, 0.8], [300, 300, 400, 400, 0.7]],
        dtype=np.float32,
    )
    assert pad._nms(dets, 0.4) == [0, 2]


def test_softmax_rows_sum_to_one_and_stable():
    out = pad._softmax(np.array([[1000.0, 1001.0], [0.0, 0.0]]))
    assert np.allclose(out.sum(axis=-1), 1.0)
    assert np.all(np.isfinite(out))
    assert out[1, 0] == pytest.approx(0.5)
    assert out[0, 1] > out[0, 0]


class FakeIO:
    def __init__(self, name, shape=None):
        self.name, self.shape = name, shape


class FakeSession:
    def __init__(self, logits=((0.0, 2.0, 0.0),)):
        self.logits = np.array(logits, dtype=np.float32)
        self.fed = None

    def get_inputs(self):
        return [FakeIO("in", [1, 3, 80, 64])]  # N, C, H, W → kích thước (W=64, H=80)

    def get_outputs(self):
        return [FakeIO("out")]

    def run(self, outputs, feed):
        self.fed = feed["in"]
        return [self.logits]


def test_classifier_crop_has_model_input_size():
    clf = pad.MiniFasNetClassifier(FakeSession())
    image = np.random.default_rng(1).integers(0, 255, (200, 300, 3), dtype=np.uint8)
    for b in (box(60), FaceBox(250, 150, 299, 199, 0.9), FaceBox(0, 0, 300, 200, 0.9)):
        assert clf._crop(image, b).shape == (80, 64, 3)


def test_classifier_p_real_uses_label_one_and_nchw_float32():
    session = FakeSession(((0.0, 2.0, 0.0),))
    clf = pad.MiniFasNetClassifier(session)
    p = clf.p_real(np.zeros((200, 300, 3), np.uint8), box(60))
    assert p == pytest.approx(float(np.exp(2.0) / (2 + np.exp(2.0))))
    assert session.fed.shape == (1, 3, 80, 64) and session.fed.dtype == np.float32


# ── thật (cần trọng số) ──────────────────────────────────────────────────────────────────
@pytest.mark.slow
@pytest.mark.parametrize("kind", ["noise", "flat"])
def test_real_weights_never_error_on_faceless_image(tmp_path, kind):
    pytest.importorskip("onnxruntime")
    models = Path(os.environ.get("MODELS_DIR") or r"D:\Projects\vericlue-store\models")
    needed = (models / "minifasnet" / "minifasnet_v2.onnx", models / "scrfd-10g" / "det_10g.onnx")
    if not all(p.is_file() for p in needed):
        pytest.skip("thiếu trọng số minifasnet / scrfd-10g")
    if kind == "noise":
        img = np.random.default_rng(3).integers(0, 255, (480, 640, 3), dtype=np.uint8)
    else:
        img = np.full((480, 640, 3), 127, np.uint8)
    path = tmp_path / "x.png"
    assert cv2.imwrite(str(path), img)
    result = FacePadDetector(models).predict(DetectorInput(images=[path]))
    assert result.status in {Status.OK, Status.NOT_APPLICABLE}
    valid(result)
