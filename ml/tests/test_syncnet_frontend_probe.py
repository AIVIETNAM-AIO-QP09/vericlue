"""Offline probe plumbing with real synthetic JPEGs and weight-free components."""

from __future__ import annotations

import importlib
import importlib.util

import numpy as np
import pytest

from vericlue_ml.common.av_recording import AVRecording, EncodedVideoFrame
from vericlue_ml.face.pad import FaceBox
from vericlue_ml.voice import av_lipsync
from vericlue_ml.voice.syncnet import SyncNetError


def _probe():
    name = "vericlue_ml.eval.syncnet_frontend_probe"
    assert importlib.util.find_spec(name) is not None, "Offline frontend probe is not implemented"
    return importlib.import_module(name)


def _recording(times: list[float] | None = None) -> AVRecording:
    cv2 = pytest.importorskip("cv2")
    if times is None:
        times = [index / 25 - 0.16 for index in range(40)]
    frames = []
    for index, at_s in enumerate(times):
        pixels = np.full((24, 32, 3), index, dtype=np.uint8)
        success, jpeg = cv2.imencode(".jpg", pixels)
        assert success
        frames.append(EncodedVideoFrame(at_s, bytearray(jpeg.tobytes())))
    return AVRecording(
        np.linspace(-0.1, 0.1, 32000, dtype=np.float32),
        16000,
        frames,
        {"clock": av_lipsync.CLOCK, "hardware_sync_verified": False},
    )


class FakeFinder:
    _input_size = 512
    _scale = 128.0
    _swap_rb = True

    def __init__(self, events: list, overrides: dict | None = None) -> None:
        self.events, self.overrides = events, overrides or {}
        self.frames = []

    def find(self, image):
        index = len(self.frames)
        self.events.append(("find", index))
        self.frames.append(image.copy())
        return self.overrides.get(index, [FaceBox(0, 0, 32, 24, 0.9)])


class FakeLandmarkProvider:
    color_order = "rgb"

    def __init__(self, events: list) -> None:
        self.events = events
        self.boxes = []
        self.frames = []

    def predict(self, image, bbox):
        index = len(self.boxes)
        self.events.append(("landmark", index))
        self.boxes.append(bbox.copy())
        self.frames.append(image.copy())
        return np.full((106, 2), index, dtype=np.float32)


class FakeFrontend:
    warp_dtype = "float32"

    def __init__(self, events: list) -> None:
        self.events = events
        self.calls = []

    def reset(self):
        self.events.append(("reset",))

    def align_frame(self, image, landmarks, *, frame_index):
        self.events.append(("align", frame_index))
        self.calls.append(frame_index)
        np.testing.assert_array_equal(landmarks, np.float32(frame_index))
        return np.full((256, 256, 3), frame_index, dtype=np.uint8)


def _components(overrides=None):
    events = []
    return FakeFinder(events, overrides), FakeLandmarkProvider(events), FakeFrontend(events), events


def _prepare(take, starts, components):
    finder, provider, frontend, _ = components
    return _probe().prepare_frontend_probe(
        take, starts, finder=finder, landmark_provider=provider, frontend=frontend
    )


def test_probe_processes_every_frame_including_unselected_preroll_and_tail() -> None:
    take, components = _recording(), _components()
    audio_before = take.samples.tobytes()
    video_before = [(frame.at_s, bytes(frame.jpeg)) for frame in take.frames]
    metadata_before = take.metadata.copy()

    result = _prepare(take, [0, 3], components)

    events = components[-1]
    assert events == [("reset",)] + [
        (kind, index) for index in range(40) for kind in ("find", "landmark", "align")
    ]
    assert [[int(crop[0, 0, 0]) for crop in window] for window in result.windows] == [
        list(range(4, 20)),
        list(range(7, 23)),
    ]
    assert result.counts == {
        "decoded_frames": 40,
        "aligned_frames": 40,
        "selected_frames": 19,
        "windows": 2,
    }
    assert take.samples.tobytes() == audio_before
    assert [(frame.at_s, bytes(frame.jpeg)) for frame in take.frames] == video_before
    assert take.metadata == metadata_before
    assert "array(" not in repr(result)


@pytest.mark.parametrize("times", [None, [index / 25 - 0.02 for index in range(32)]])
def test_selected_pts_indices_match_existing_read_ram_windows(times) -> None:
    take = _recording(times)
    # Baseline crops retain each real grayscale JPEG's frame-index pixel value.
    baseline = av_lipsync.read_ram_windows(take, [0, 4], FakeFinder([]))
    result = _prepare(take, [0, 4], _components())
    baseline_ids = [[int(crop[0, 0, 0]) for crop in window] for window in baseline]
    candidate_ids = [[int(crop[0, 0, 0]) for crop in window] for window in result.windows]
    assert candidate_ids == baseline_ids
    if times is not None:
        assert candidate_ids[0][0] == 0  # Exact equidistant tie at zero picks the earlier frame.


def test_probe_preserves_declared_window_order() -> None:
    result = _prepare(_recording(), [4, 0], _components())
    assert [int(window[0][0, 0, 0]) for window in result.windows] == [8, 4]


def test_rgb_is_passed_once_and_selected_bbox_keeps_float32_precision() -> None:
    cv2 = pytest.importorskip("cv2")
    take = _recording()
    success, encoded = cv2.imencode(".jpg", np.full((24, 32, 3), [15, 80, 200], dtype=np.uint8))
    assert success
    take.frames[0].jpeg = bytearray(encoded.tobytes())
    smaller = FaceBox(0, 0, 2, 2, 0.9)
    largest = FaceBox(1.123456789, 2.234567891, 30.345678912, 23.456789123, 0.9)
    components = _components({0: [smaller, largest]})

    _prepare(take, [0], components)

    expected_rgb = cv2.imdecode(encoded, cv2.IMREAD_COLOR)[:, :, ::-1]
    finder, provider, _, _ = components
    np.testing.assert_array_equal(finder.frames[0], expected_rgb)
    np.testing.assert_array_equal(provider.frames[0], expected_rgb)
    assert provider.boxes[0].dtype == np.float32
    np.testing.assert_array_equal(
        provider.boxes[0],
        np.array([1.123456789, 2.234567891, 30.345678912, 23.456789123], dtype=np.float32),
    )


@pytest.mark.parametrize(
    "faces,code",
    [([], "E_NO_FACE"), ([FaceBox(0, 0, 20, 20, 0.9), FaceBox(0, 0, 10, 20, 0.8)], "E_MULTI_FACE")],
)
def test_no_face_or_ambiguous_unused_tail_fails_the_entire_probe(faces, code) -> None:
    components = _components({35: faces})
    with pytest.raises(SyncNetError) as caught:
        _prepare(_recording(), [0], components)
    assert caught.value.code == code
    assert components[2].calls == list(range(35))


def test_invalid_unused_tail_jpeg_is_not_silently_ignored() -> None:
    take, components = _recording(), _components()
    take.frames[35].jpeg = bytearray(b"not-a-jpeg")
    with pytest.raises(SyncNetError, match="JPEG"):
        _prepare(take, [0], components)
    assert components[2].calls == list(range(35))


def test_selected_timestamp_gap_fails_like_baseline() -> None:
    take = _recording([0.0, 0.2] + [index / 25 for index in range(6, 35)])
    with pytest.raises(SyncNetError) as original:
        av_lipsync.read_ram_windows(take, [0], FakeFinder([]))
    with pytest.raises(SyncNetError) as candidate:
        _prepare(take, [0], _components())
    assert candidate.value.code == original.value.code == "E_LOW_QUALITY"
    assert candidate.value.status == original.value.status == "degraded"


@pytest.mark.parametrize("first_at,accepted", [(0.0400009, True), (0.040002, False)])
def test_original_40ms_tolerance_and_epsilon_are_preserved(first_at, accepted) -> None:
    take = _recording([first_at + index / 25 for index in range(20)])
    if accepted:
        result = _prepare(take, [0], _components())
        assert len(result.windows[0]) == 16
    else:
        with pytest.raises(SyncNetError):
            _prepare(take, [0], _components())


@pytest.mark.parametrize(
    "starts", [[], [-1], [True], [0.0], [float("nan")], [10**1000], [0, 1, 2, 3, 4]]
)
def test_invalid_or_unbounded_starts_fail_before_any_component_calls(starts) -> None:
    components = _components()
    with pytest.raises(SyncNetError):
        _prepare(_recording(), starts, components)
    assert components[-1] == []


@pytest.mark.parametrize("broken", ["clock", "audio", "timestamps"])
def test_recording_validation_is_reused_before_any_component_calls(broken) -> None:
    take, components = _recording(), _components()
    if broken == "clock":
        take.metadata["clock"] = "independent-clock"
    elif broken == "audio":
        take.samples[0] = np.nan
    else:
        take.frames[1].at_s = take.frames[0].at_s
    with pytest.raises(SyncNetError):
        _prepare(take, [0], components)
    assert components[-1] == []


@pytest.mark.parametrize(
    "component,field,value",
    [
        (0, "_input_size", 640),
        (0, "_scale", 127.5),
        (0, "_swap_rb", False),
        (1, "color_order", "bgr"),
        (2, "warp_dtype", "float16"),
    ],
)
def test_probe_rejects_a_different_preprocessing_variant(component, field, value) -> None:
    components = _components()
    setattr(components[component], field, value)
    with pytest.raises(SyncNetError):
        _prepare(_recording(), [0], components)
    assert components[-1] == []


@pytest.mark.parametrize("box", [FaceBox(np.nan, 0, 20, 20, 0.9), FaceBox(4, 0, 4, 20, 0.9)])
def test_invalid_face_geometry_fails_before_landmark_prediction(box) -> None:
    components = _components({0: [box]})
    with pytest.raises(SyncNetError):
        _prepare(_recording(), [0], components)
    assert components[1].boxes == []
