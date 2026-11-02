"""Original-file streaming probe oracles, without files, codecs or models."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
from test_syncnet_frontend_probe import _components

from vericlue_ml.face.pad import FaceBox
from vericlue_ml.voice import syncnet


def _probe():
    name = "vericlue_ml.eval.syncnet_file_frontend_probe"
    assert importlib.util.find_spec(name) is not None, (
        "Original-file frontend probe is not implemented"
    )
    return importlib.import_module(name)


@pytest.fixture
def fake_video(monkeypatch):
    def install(times, *, opened=True, broken_images=None):
        captures = []
        cv2 = ModuleType("cv2")
        cv2.CAP_PROP_POS_MSEC = 0
        cv2.COLOR_BGR2RGB = 1

        class Capture:
            def __init__(self, path):
                self.position = -1
                self.released = False
                self.path = path
                captures.append(self)

            def isOpened(self):
                return opened

            def read(self):
                self.position += 1
                if self.position >= len(times):
                    return False, None
                if broken_images and self.position in broken_images:
                    return True, broken_images[self.position]
                return True, np.full((24, 32, 3), self.position, dtype=np.uint8)

            def get(self, prop):
                assert prop == cv2.CAP_PROP_POS_MSEC, "Use decoded PTS, not FPS/count metadata"
                return times[self.position] * 1000

            def set(self, *args):
                raise AssertionError("Do not seek or resize the original video")

            def release(self):
                self.released = True

        def to_rgb(image, code):
            assert code == cv2.COLOR_BGR2RGB
            return np.ascontiguousarray(image[:, :, ::-1])

        cv2.VideoCapture = Capture
        cv2.cvtColor = to_rgb
        # No imencode/imdecode/resize API exists in this fixture deliberately.
        monkeypatch.setitem(sys.modules, "cv2", cv2)
        monkeypatch.setattr(syncnet, "_face_crop", lambda image, finder: int(image[0, 0, 0]))
        return captures

    return install


def _prepare(starts, components, *, audio_offset_s=0):
    finder, provider, frontend, _ = components
    return _probe().prepare_file_frontend_probe(
        Path("private-original-video.mp4"),
        starts,
        audio_offset_s=audio_offset_s,
        finder=finder,
        landmark_provider=provider,
        frontend=frontend,
    )


@pytest.mark.parametrize(
    "times,starts,offset",
    [
        (
            [
                0.0,
                0.018,
                0.05,
                0.081,
                0.112,
                0.158,
                0.201,
                0.242,
                0.281,
                0.324,
                0.359,
                0.404,
                0.439,
                0.479,
                0.523,
                0.56,
                0.602,
                0.643,
                0.681,
            ],
            [1, 0],
            0,
        ),
        ([index / 25 for index in range(40)], [0], 0.2),
        ([index / 25 for index in range(40)], [5], -0.2),
        ([0.0, 0.08] + [index / 25 for index in range(3, 30)], [0], 0),
        ([index / 25 for index in range(15)] + [0.58], [0], 0),
    ],
)
def test_streaming_pts_selection_matches_file_baseline_including_ties_and_eof(
    fake_video, times, starts, offset
) -> None:
    captures = fake_video(times)
    baseline = syncnet._read_windows(
        Path("private-original-video.mp4"), starts, object(), audio_offset_s=offset
    )
    components = _components()

    result = _prepare(starts, components, audio_offset_s=offset)

    assert [[int(image[0, 0, 0]) for image in window] for window in result.windows] == baseline
    assert components[2].calls == list(range(len(times)))
    assert all(capture.released for capture in captures)
    assert result.counts == {
        "decoded_frames": len(times),
        "aligned_frames": len(times),
        "selected_frames": len({index for window in baseline for index in window}),
        "windows": len(starts),
    }
    assert result.provenance["pipeline"] == "original-file-opencv-pts-v1"
    assert result.provenance["audio_offset_s"] == offset
    assert "private-original-video" not in repr(result)
    assert "array(" not in repr(result)


def test_entire_tail_is_processed_after_last_requested_frame(fake_video) -> None:
    captures = fake_video([index / 25 for index in range(40)])
    components = _components()
    result = _prepare([0], components)
    assert components[-1] == [("reset",)] + [
        (kind, index) for index in range(40) for kind in ("find", "landmark", "align")
    ]
    assert [int(image[0, 0, 0]) for image in result.windows[0]] == list(range(16))
    assert captures[0].position == 40
    assert captures[0].released


def test_decoded_original_pixels_keep_dimensions_and_reverse_channels_once(fake_video) -> None:
    pixels = np.full((73, 119, 3), [10, 70, 200], dtype=np.uint8)
    fake_video([index / 25 for index in range(20)], broken_images={0: pixels})
    components = _components()
    _prepare([0], components)
    for frame in (components[0].frames[0], components[1].frames[0]):
        assert frame.shape == (73, 119, 3)
        np.testing.assert_array_equal(frame[0, 0], [200, 70, 10])
    np.testing.assert_array_equal(pixels[0, 0], [10, 70, 200])


@pytest.mark.parametrize(
    "bad_times", [[float("nan")], [float("inf")], [-0.01], [0.0, 0.0], [0.0, 0.04, 0.03]]
)
def test_invalid_pts_match_baseline_fail_closed_and_release(fake_video, bad_times) -> None:
    captures = fake_video(bad_times)
    with pytest.raises(syncnet.SyncNetError) as baseline:
        syncnet._read_windows(Path("source.mp4"), [0], object())
    with pytest.raises(syncnet.SyncNetError) as probe:
        _prepare([0], _components())
    assert probe.value.code == baseline.value.code == "E_LOW_QUALITY"
    assert probe.value.status == baseline.value.status == "degraded"
    assert all(capture.released for capture in captures)


@pytest.mark.parametrize(
    "times", [[0.0, 0.2, 0.4, 0.6], [index / 25 for index in range(14)] + [0.55], []]
)
def test_gap_or_insufficient_eof_matches_file_baseline(fake_video, times) -> None:
    captures = fake_video(times)
    with pytest.raises(syncnet.SyncNetError) as baseline:
        syncnet._read_windows(Path("source.mp4"), [0], object())
    with pytest.raises(syncnet.SyncNetError) as probe:
        _prepare([0], _components())
    assert (probe.value.code, probe.value.status) == (baseline.value.code, baseline.value.status)
    assert all(capture.released for capture in captures)


@pytest.mark.parametrize("last_at,accepted", [(0.5599991, True), (0.559998, False)])
def test_eof_preserves_40ms_plus_epsilon_tolerance(fake_video, last_at, accepted) -> None:
    captures = fake_video([index / 25 for index in range(14)] + [last_at])
    if accepted:
        assert len(_prepare([0], _components()).windows[0]) == 16
    else:
        with pytest.raises(syncnet.SyncNetError) as failure:
            _prepare([0], _components())
        assert failure.value.code == "E_LOW_QUALITY"
    assert captures[0].released


@pytest.mark.parametrize("failure", ["no_face", "multi_face", "timestamp", "frame"])
def test_invalid_unused_tail_prevents_any_result_and_releases(fake_video, failure) -> None:
    times = [index / 25 for index in range(40)]
    broken_images = {35: None} if failure == "frame" else None
    if failure == "timestamp":
        times[35] = times[34]
    overrides = {}
    if failure == "no_face":
        overrides[35] = []
    if failure == "multi_face":
        overrides[35] = [FaceBox(0, 0, 20, 20, 0.9), FaceBox(0, 0, 10, 20, 0.8)]
    captures = fake_video(times, broken_images=broken_images)
    components = _components(overrides)
    with pytest.raises(syncnet.SyncNetError):
        _prepare([0], components)
    assert components[2].calls == list(range(35))
    assert captures[0].released


@pytest.mark.parametrize(
    "starts,offset",
    [
        ([], 0),
        ([True], 0),
        ([0.5], 0),
        ([-1], 0),
        ([10**1000], 0),
        ([0, 1, 2, 3, 4], 0),
        ([0], float("nan")),
        ([0], float("inf")),
        ([0], -0.1),
        ([0], 21),
    ],
)
def test_invalid_or_unbounded_requests_do_not_open_video_or_reset_components(
    fake_video, starts, offset
) -> None:
    captures, components = fake_video([0]), _components()
    with pytest.raises(syncnet.SyncNetError):
        _prepare(starts, components, audio_offset_s=offset)
    assert captures == []
    assert components[-1] == []


def test_closed_capture_fails_and_is_released(fake_video) -> None:
    captures = fake_video([], opened=False)
    with pytest.raises(syncnet.SyncNetError):
        _prepare([0], _components())
    assert captures[0].released


def test_original_video_duration_budget_applies_to_unused_tail(fake_video) -> None:
    captures = fake_video([index / 25 for index in range(20)] + [21.001])
    with pytest.raises(syncnet.SyncNetError) as failure:
        _prepare([0], _components())
    assert failure.value.code == "E_DECODE"
    assert captures[0].released


def test_decoded_frame_budget_applies_to_unused_tail(fake_video, monkeypatch) -> None:
    probe = _probe()
    monkeypatch.setattr(probe, "MAX_FILE_FRAMES", 18)
    captures, components = fake_video([index / 25 for index in range(20)]), _components()
    with pytest.raises(syncnet.SyncNetError, match="frames"):
        _prepare([0], components)
    assert len(components[2].calls) == 18
    assert captures[0].released


def test_oversized_original_frame_is_rejected_without_resizing(fake_video) -> None:
    captures = fake_video([0], broken_images={0: np.zeros((1081, 1920, 3), dtype=np.uint8)})
    components = _components()
    with pytest.raises(syncnet.SyncNetError):
        _prepare([0], components)
    assert components[0].frames == []
    assert captures[0].released
