"""Freeze the offline landmark boundary without weights, native ORT or biometric data."""

import hashlib
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.voice import landmarks106


class FakeSession:
    def __init__(self):
        self.inputs = [SimpleNamespace(name="data", shape=[1, 3, 192, 192], type="tensor(float)")]
        self.outputs = [SimpleNamespace(name="fc1", shape=[1, 212], type="tensor(float)")]
        self.result = [np.zeros((1, 212), dtype=np.float32)]
        self.feeds = []

    def get_inputs(self):
        return self.inputs

    def get_outputs(self):
        return self.outputs

    def run(self, names, feeds):
        assert names == ["fc1"]
        assert set(feeds) == {"data"}
        self.feeds.append(feeds["data"].copy())
        return self.result


@pytest.fixture
def backend(monkeypatch, tmp_path):
    content = b"synthetic-landmark106-artifact"
    path = tmp_path / "landmarks.onnx"
    path.write_bytes(content)
    monkeypatch.setattr(landmarks106, "MODEL_SHA256", hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(landmarks106, "MODEL_SIZE_BYTES", len(content))
    session = FakeSession()
    loads = []

    def create(model, *, sess_options, providers):
        loads.append((model, providers))
        assert sess_options.intra_op_num_threads == 1
        assert sess_options.inter_op_num_threads == 1
        return session

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(InferenceSession=create, SessionOptions=SimpleNamespace),
    )
    return SimpleNamespace(path=path, content=content, session=session, loads=loads)


def test_verified_bytes_load_once_on_cpu_and_repeated_calls_reuse_session(backend):
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    frame = np.zeros((192, 192, 3), dtype=np.uint8)
    for _ in range(2):
        result = provider.predict(frame, (32, 32, 160, 160))
        np.testing.assert_array_equal(result, np.full((106, 2), 96, dtype=np.float32))
        assert result.dtype == np.float32
    assert backend.loads == [(backend.content, ["CPUExecutionProvider"])]
    assert len(backend.session.feeds) == 2


@pytest.mark.parametrize("mutation", ["same_size_corruption", "truncated", "missing"])
def test_bad_artifact_is_rejected_before_ort_load(backend, mutation):
    if mutation == "same_size_corruption":
        backend.path.write_bytes(b"!" * len(backend.content))
    elif mutation == "truncated":
        backend.path.write_bytes(backend.content[:-1])
    else:
        backend.path.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    assert backend.loads == []


@pytest.mark.parametrize("batch", [None, "batch", 1])
def test_single_sample_accepts_symbolic_batch_metadata(backend, batch):
    backend.session.inputs[0].shape[0] = batch
    backend.session.outputs[0].shape[0] = batch
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    assert provider.predict(np.zeros((8, 8, 3), np.uint8), (0, 0, 8, 8)).shape == (106, 2)


@pytest.mark.parametrize(
    ("which", "field", "value"),
    [
        ("inputs", "shape", [1, 192, 192, 3]),
        ("inputs", "shape", [1, 3, 224, 224]),
        ("inputs", "shape", [2, 3, 192, 192]),
        ("inputs", "type", "tensor(double)"),
        ("outputs", "shape", [1, 210]),
        ("outputs", "shape", [1, 106, 2]),
        ("outputs", "shape", [2, 212]),
        ("outputs", "type", "tensor(double)"),
    ],
)
def test_invalid_model_metadata_is_rejected(backend, which, field, value):
    setattr(getattr(backend.session, which)[0], field, value)
    with pytest.raises(ValueError):
        landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    assert backend.session.feeds == []


@pytest.mark.parametrize(
    ("which", "count"), [("inputs", 0), ("inputs", 2), ("outputs", 0), ("outputs", 2)]
)
def test_model_requires_exactly_one_input_and_one_output(backend, which, count):
    setattr(backend.session, which, getattr(backend.session, which) * count)
    with pytest.raises(ValueError):
        landmarks106.Landmark106Provider(backend.path, color_order="rgb")


@pytest.mark.parametrize("color_order", ["RGB", "gray", None])
def test_color_order_must_be_explicitly_rgb_or_bgr(backend, color_order):
    with pytest.raises(ValueError):
        landmarks106.Landmark106Provider(backend.path, color_order=color_order)
    assert backend.loads == []


def test_crop_inverse_maps_all_points_without_rounding_or_clipping(backend):
    raw = backend.session.result[0].reshape(106, 2)
    raw[:4] = [[-1, -1], [0, 0], [1, 1], [0.125, -0.375]]
    original = raw.copy()
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    result = provider.predict(np.zeros((128, 192, 3), np.uint8), (80, 40, 144, 88))
    np.testing.assert_array_equal(result[:4], [[64, 16], [112, 64], [160, 112], [118, 46]])
    np.testing.assert_array_equal(raw, original)


@pytest.mark.parametrize(
    ("color_order", "expected_pixel"),
    [("rgb", [64, 11, 7]), ("bgr", [7, 11, 64])],
)
def test_rgb_and_bgr_callers_reverse_channels_once_without_external_normalization(
    backend, color_order, expected_pixel
):
    # A 128-side box centered at (96,96) produces an identity 192-side crop.
    yy, xx = np.indices((192, 192), dtype=np.uint8)
    rgb = np.stack((xx, yy, np.full_like(xx, 64)), axis=-1)
    frame = rgb if color_order == "rgb" else rgb[..., ::-1]
    original = frame.copy()
    provider = landmarks106.Landmark106Provider(backend.path, color_order=color_order)
    provider.predict(frame, (32, 32, 160, 160))
    blob = backend.session.feeds[0]
    assert blob.shape == (1, 3, 192, 192)
    assert blob.dtype == np.float32 and blob.flags.c_contiguous
    np.testing.assert_array_equal(blob[0, :, 11, 7], expected_pixel)
    np.testing.assert_array_equal(blob[0], frame[..., ::-1].transpose(2, 0, 1))
    np.testing.assert_array_equal(frame, original)


def test_fractional_crop_uses_bilinear_interpolation_and_zero_padding(backend):
    # Scale 1, translation (+0.5,+0.5): output (1,1) samples source (0.5,0.5).
    frame = np.zeros((192, 192, 3), np.uint8)
    frame[:2, :2] = [[[0, 0, 0], [40, 80, 120]], [[80, 120, 160], [120, 160, 200]]]
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    provider.predict(frame, (31.5, 31.5, 159.5, 159.5))
    blob = backend.session.feeds[0]
    np.testing.assert_array_equal(blob[0, :, 1, 1], [120, 90, 60])
    np.testing.assert_array_equal(blob[0, :, 0, 1], [30, 20, 10])
    np.testing.assert_array_equal(blob[0, :, 0, 0], [0, 0, 0])


def test_crop_uses_longer_side_with_bilinear_scale(backend):
    # Box 64x48 centered at (112,64): scale2, inverse maps (1,1) to (64.5,16.5).
    yy, xx = np.indices((128, 192), dtype=np.uint8)
    frame = np.stack((2 * xx, 2 * yy, np.full_like(xx, 64)), axis=-1)
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    provider.predict(frame, (80, 40, 144, 88))
    np.testing.assert_array_equal(backend.session.feeds[0][0, :, 1, 1], [64, 33, 129])


def test_box_outside_frame_is_zero_padded_not_clamped(backend):
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    points = provider.predict(np.full((8, 8, 3), 255, np.uint8), (-192, -192, -64, -64))
    np.testing.assert_array_equal(points, np.full((106, 2), -128, np.float32))
    np.testing.assert_array_equal(backend.session.feeds[0], np.zeros((1, 3, 192, 192)))


@pytest.mark.skipif(
    not isinstance(np.float32(1) / 2, np.float32),
    reason="The recorded original-source oracle uses NumPy 2 float32 scalar promotion",
)
def test_float32_fractional_bbox_matches_original_mit_crop_matrix(backend):
    import cv2

    # Unchanged InsightFace 3e648694, fake ORT oracle case 16, NumPy 2.5.4.
    # A prior float64 bbox promotion changed 292 tensor elements (max 7 bytes).
    bbox = np.array(
        [18.962520599365234, 134.23080444335938, 157.07432556152344, 279.050537109375],
        dtype=np.float32,
    )
    original_matrix = np.array(
        [[0.8838574290275574, 0, 18.204261779785156], [0, 0.8838574290275574, -86.64088439941406]],
        dtype=np.float64,
    )
    yy, xx = np.indices((240, 320))
    frame = np.stack(
        ((37 * xx + 13 * yy) % 256, (11 * xx + 53 * yy) % 256, (97 * xx + 7 * yy) % 256),
        axis=-1,
    ).astype(np.uint8)
    original_crop = cv2.warpAffine(frame, original_matrix, (192, 192), borderValue=0)
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    provider.predict(frame, bbox)
    np.testing.assert_array_equal(
        backend.session.feeds[0][0], original_crop[..., ::-1].transpose(2, 0, 1)
    )


@pytest.mark.skipif(
    not isinstance(np.float32(1) / 2, np.float32),
    reason="The recorded original-source oracle uses NumPy 2 float32 scalar promotion",
)
def test_float32_fractional_bbox_matches_original_mit_coordinate_assignment(backend):
    # Unchanged InsightFace 3e648694, fake ORT oracle case 0, NumPy 2.5.4.
    backend.session.result = [np.linspace(-0.8, 0.8, 212, dtype=np.float32).reshape(1, 212)]
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    result = provider.predict(
        np.zeros((240, 320, 3), np.uint8), np.array([32.1, 32.2, 160.3, 160.4], np.float32)
    )
    np.testing.assert_array_equal(
        result[[0, 1, 52, 105]],
        np.array(
            [
                [19.27998924255371, 20.109086990356445],
                [20.738187789916992, 21.567283630371094],
                [95.10635375976562, 95.93544006347656],
                [172.39089965820312, 173.21998596191406],
            ],
            dtype=np.float32,
        ),
    )


@pytest.mark.parametrize(
    "bbox",
    [
        (),
        (1, 2, 3),
        ((1, 2, 3, 4),),
        ((0, 0, 4, 4), (8, 8, 12, 12)),
        (1, 2, 1, 4),
        (1, 4, 3, 2),
        (0, 0, np.nan, 4),
        (0, 0, np.inf, 4),
        (0, 0, "bad", 4),
        (0, 0, 1e200, 1e200),
        (0, 0, 1e-200, 1e-200),
    ],
)
def test_invalid_or_multiple_bounding_boxes_never_reach_inference(backend, bbox):
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    with pytest.raises(ValueError):
        provider.predict(np.zeros((16, 16, 3), np.uint8), bbox)
    assert backend.session.feeds == []


@pytest.mark.parametrize(
    "frame",
    [
        np.zeros((0, 16, 3), np.uint8),
        np.zeros((16, 0, 3), np.uint8),
        np.zeros((16, 16), np.uint8),
        np.zeros((16, 16, 4), np.uint8),
        np.zeros((16, 16, 3), np.float32),
        np.full((16, 16, 3), np.nan),
    ],
)
def test_invalid_frame_never_reaches_inference(backend, frame):
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    with pytest.raises(ValueError):
        provider.predict(frame, (0, 0, 16, 16))
    assert backend.session.feeds == []


@pytest.mark.parametrize(
    "output",
    [
        [],
        [np.zeros((1, 212), np.float32)] * 2,
        [np.zeros(212, np.float32)],
        [np.zeros((1, 106, 2), np.float32)],
        [np.zeros((2, 212), np.float32)],
        [np.zeros((1, 210), np.float32)],
        [np.full((1, 212), np.nan, np.float32)],
        [np.full((1, 212), np.inf, np.float32)],
        [np.full((1, 212), np.finfo(np.float32).max, np.float32)],
        [np.zeros((1, 212), np.int32)],
    ],
)
def test_invalid_model_output_has_no_fabricated_landmarks(backend, output):
    backend.session.result = output
    provider = landmarks106.Landmark106Provider(backend.path, color_order="rgb")
    with pytest.raises(ValueError):
        provider.predict(np.zeros((16, 16, 3), np.uint8), (0, 0, 16, 16))
