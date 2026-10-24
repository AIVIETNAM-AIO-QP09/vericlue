"""Native-reader-independent tests: timestamp selection, bounds and decoder cleanup."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.result import ErrorCode, Status
from vericlue_ml.presence.landmarks import LandmarkError
from vericlue_ml.presence.views import select_video_frames, video_sha256

TARGETS = {"front": 100.0, "left": 400.0, "right": 700.0}


def decoder(monkeypatch, tmp_path, times, *, shape=(24, 32, 3), opened=True):
    path = tmp_path / "synthetic.webm"
    path.write_bytes(b"\x1aE\xdf\xa3" + b"\0" * 12)
    handles = []

    class Capture:
        def __init__(self, source):
            assert source == str(path)
            self.index, self.released = -1, False
            handles.append(self)

        def isOpened(self):
            return opened

        def read(self):
            self.index += 1
            return (
                (True, np.full(shape, self.index % 256, dtype=np.uint8))
                if self.index < len(times)
                else (False, None)
            )

        def get(self, key):
            assert key == 1  # Never FPS/seek/frame count.
            return times[self.index]

        def release(self):
            self.released = True

    monkeypatch.setitem(
        sys.modules, "cv2", SimpleNamespace(VideoCapture=Capture, CAP_PROP_POS_MSEC=1)
    )
    return path, handles


def test_nearest_frames_use_actual_vfr_timestamps_and_earlier_tie(monkeypatch, tmp_path):
    path, handles = decoder(monkeypatch, tmp_path, [0, 80, 120, 280, 395, 600, 710, 850])
    frames = select_video_frames(path, TARGETS)
    assert {role: value.at_ms for role, value in frames.items()} == {
        "front": 80,
        "left": 395,
        "right": 710,
    }
    assert frames["front"].bgr[0, 0, 0] == 1
    assert all(h.released for h in handles)
    assert len(list(tmp_path.iterdir())) == 1  # No frame files written.


@pytest.mark.parametrize("times", [[0, 0], [0, 100, 50], [float("nan")], [-1], [1000]])
def test_invalid_decoder_timestamps_never_fall_back_to_fps(monkeypatch, tmp_path, times):
    path, handles = decoder(monkeypatch, tmp_path, times)
    with pytest.raises(LandmarkError):
        select_video_frames(path, TARGETS)
    assert all(h.released for h in handles)


@pytest.mark.parametrize("times", [[0, 100], [0, 100, 400, 900]])
def test_short_video_or_gap_cannot_supply_all_views(monkeypatch, tmp_path, times):
    path, handles = decoder(monkeypatch, tmp_path, times)
    with pytest.raises(LandmarkError) as exc:
        select_video_frames(path, TARGETS)
    assert exc.value.status == Status.DEGRADED
    assert all(h.released for h in handles)


def test_same_decoded_frame_cannot_count_as_two_views(monkeypatch, tmp_path):
    path, handles = decoder(monkeypatch, tmp_path, [0, 100, 400, 700])
    with pytest.raises(LandmarkError) as exc:
        select_video_frames(path, {"front": 100, "left": 110, "right": 700})
    assert exc.value.code == ErrorCode.E_INTEGRITY
    assert all(h.released for h in handles)


@pytest.mark.parametrize("shape", [(1081, 1920, 3), (20, 30), (20, 30, 4)])
def test_invalid_or_excessive_frame_dimensions_rejected(monkeypatch, tmp_path, shape):
    path, handles = decoder(monkeypatch, tmp_path, [0], shape=shape)
    with pytest.raises(LandmarkError):
        select_video_frames(path, TARGETS)
    assert all(h.released for h in handles)


def test_failed_open_closes_decoder(monkeypatch, tmp_path):
    path, handles = decoder(monkeypatch, tmp_path, [], opened=False)
    with pytest.raises(LandmarkError):
        select_video_frames(path, TARGETS)
    assert handles[0].released


def test_frame_and_wall_time_budgets_release_decoder(monkeypatch, tmp_path):
    from vericlue_ml.presence import views

    path, handles = decoder(monkeypatch, tmp_path, [0, 100, 200, 300])
    monkeypatch.setattr(views, "MAX_VIDEO_FRAMES", 2)
    with pytest.raises(LandmarkError) as exc:
        select_video_frames(path, TARGETS)
    assert exc.value.code == ErrorCode.E_TIMEOUT and handles[-1].released
    ticks = iter([0, 16])
    monkeypatch.setattr(views, "perf_counter", lambda: next(ticks))
    with pytest.raises(LandmarkError) as exc:
        select_video_frames(path, TARGETS)
    assert exc.value.code == ErrorCode.E_TIMEOUT and handles[-1].released


def test_playlist_and_oversized_video_rejected_before_native_open(monkeypatch, tmp_path):
    from vericlue_ml.presence import views

    path = tmp_path / "fake.webm"
    path.write_bytes(b"#EXTM3U\nhttps://example.invalid/video")
    with pytest.raises(LandmarkError):
        video_sha256(path)
    path.write_bytes(b"\x1aE\xdf\xa3" + b"\0" * 16)
    monkeypatch.setattr(views, "MAX_VIDEO_BYTES", 8)
    with pytest.raises(LandmarkError):
        video_sha256(path)


@pytest.mark.parametrize(
    "targets",
    [
        {},
        {**TARGETS, "front": True},
        {**TARGETS, "front": float("nan")},
        {**TARGETS, "right": 400},
        {**TARGETS, "right": 31000},
    ],
)
def test_invalid_target_plan_is_rejected(tmp_path, targets):
    with pytest.raises(LandmarkError):
        select_video_frames(tmp_path / "never-opened.mp4", targets)


def test_native_mp4_decoder_selects_synthetic_views_without_writing_images(tmp_path):
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "synthetic-colors.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    assert writer.isOpened()
    try:
        for i in range(191):
            writer.write(np.full((240, 320, 3), 40 + i % 150, dtype=np.uint8))
    finally:
        writer.release()
    targets = {"front": 1000.0, "left": 13200.0, "right": 15200.0}
    frames = select_video_frames(path, targets)
    assert all(abs(frame.at_ms - targets[role]) < 1 for role, frame in frames.items())
    assert all(frame.bgr.shape == (240, 320, 3) for frame in frames.values())
    assert len(list(tmp_path.iterdir())) == 1
