"""SCRFD input-size seam with synthetic pixels and heads; no ONNX/model loading."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.face.pad import PadError, ScrfdFaceFinder


class SyntheticScrfdSession:
    """Emit one optional second-anchor detection on the requested pyramid level."""

    def __init__(self, size: int, active_stride: int | None = None) -> None:
        self.size = size
        self.active_stride = active_stride
        self.fed: list[np.ndarray] = []

    def get_inputs(self):
        return [SimpleNamespace(name="pixels", shape=[1, 3, self.size, self.size])]

    def get_outputs(self):
        return [SimpleNamespace(name=f"head-{index}") for index in range(9)]

    def run(self, names, feed):
        self.fed.append(feed["pixels"].copy())
        lengths = [2 * (self.size // stride) ** 2 for stride in (8, 16, 32)]
        scores = [np.zeros((length, 1), dtype=np.float32) for length in lengths]
        boxes = [np.zeros((length, 4), dtype=np.float32) for length in lengths]
        landmarks = [np.zeros((length, 10), dtype=np.float32) for length in lengths]
        if self.active_stride is not None:
            level = (8, 16, 32).index(self.active_stride)
            # Row3, column5, second anchor; grid width must follow detector size.
            anchor = (3 * (self.size // self.active_stride) + 5) * 2 + 1
            scores[level][anchor] = 0.9
            boxes[level][anchor] = [1, 2, 3, 4]
            landmarks[level][anchor] = [-2, -1, 2, -1, 0, 0, -1, 2, 1, 2]
        return scores + boxes + landmarks


def test_default_640_letterbox_and_tensor_bytes_remain_unchanged() -> None:
    # The image already has width640: top half is copied, bottom half is black.
    rows, columns = np.indices((320, 640))
    pixels = np.stack((columns % 256, rows % 256, (columns + rows) % 256), axis=2).astype(np.uint8)
    expected_canvas = np.zeros((640, 640, 3), dtype=np.uint8)
    expected_canvas[:320] = pixels
    expected = ((expected_canvas.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
    session = SyntheticScrfdSession(640)

    assert ScrfdFaceFinder(session).find(pixels) == []

    tensor = session.fed[0]
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert tensor.tobytes() == expected.tobytes()


def test_explicit_640_matches_default_without_changing_preprocessing() -> None:
    pixels = np.full((240, 320, 3), [19, 83, 211], dtype=np.uint8)
    default, explicit = SyntheticScrfdSession(640), SyntheticScrfdSession(640)

    ScrfdFaceFinder(default).find(pixels)
    ScrfdFaceFinder(explicit, input_size=640).find(pixels)

    assert default.fed[0].tobytes() == explicit.fed[0].tobytes()


def test_512_diagnostic_can_use_rgb_swap_and_divisor_128_explicitly() -> None:
    pixels_rgb = np.full((256, 512, 3), [10, 70, 210], dtype=np.uint8)
    session = SyntheticScrfdSession(512)
    finder = ScrfdFaceFinder(session, input_size=512, scale=128.0, swap_rb=True)

    assert finder.find(pixels_rgb) == []

    tensor = session.fed[0]
    assert tensor.shape == (1, 3, 512, 512)
    # Incoming RGB is reversed once: effective BGR at the model boundary.
    np.testing.assert_array_equal(tensor[0, :, 0, 0], [0.64453125, -0.44921875, -0.91796875])
    np.testing.assert_array_equal(tensor[0, :, 256:, :], np.float32(-0.99609375))
    np.testing.assert_array_equal(tensor[0, :, 255, -1], tensor[0, :, 0, 0])


@pytest.mark.parametrize(
    "stride,box,landmarks",
    [
        (8, (64, 16, 128, 112), ((48, 32), (112, 32), (80, 48), (64, 80), (96, 80))),
        (16, (128, 32, 256, 224), ((96, 64), (224, 64), (160, 96), (128, 160), (192, 160))),
        (32, (256, 64, 512, 448), ((192, 128), (448, 128), (320, 192), (256, 320), (384, 320))),
    ],
)
def test_512_decodes_each_head_and_landmarks_to_original_coordinates(
    stride, box, landmarks
) -> None:
    session = SyntheticScrfdSession(512, active_stride=stride)
    finder = ScrfdFaceFinder(session, input_size=512)
    # Width1024 ->512, so both decoded boxes and landmarks must double.
    pixels = np.zeros((512, 1024, 3), dtype=np.uint8)

    [face] = finder.find(pixels)

    assert (face.x1, face.y1, face.x2, face.y2) == box
    assert face.landmarks == landmarks
    assert face.confidence == pytest.approx(0.9)
    # Repeated calls use the same grid and do not change input-size state.
    assert finder.find(pixels) == [face]


@pytest.mark.parametrize("size", [0, -512, 32, 511, 513, 608, 672, 512.0, "512", True, None])
def test_invalid_size_fails_before_touching_a_session(size) -> None:
    with pytest.raises(PadError, match="512|640"):
        ScrfdFaceFinder(object(), input_size=size)
