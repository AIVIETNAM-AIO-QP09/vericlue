"""Reader timing, resource bounds and model-error behavior without native dependencies."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.result import ErrorCode, Status
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError


def fake_reader(monkeypatch, tmp_path, times, *, shape=(240, 320, 3)):
    video = tmp_path / "synthetic.webm"
    video.write_bytes(b"\x1aE\xdf\xa3" + b"\x00" * 12)
    captures = []
    predicted = []

    class Capture:
        def __init__(self, path):
            assert path == str(video)
            self.index = -1
            self.released = False
            captures.append(self)

        def isOpened(self):
            return True

        def read(self):
            self.index += 1
            return (
                (True, np.zeros(shape, dtype=np.uint8))
                if self.index < len(times)
                else (False, None)
            )

        def get(self, prop):
            assert prop == 1  # Only decoder time, never nominal FPS or frame count.
            return times[self.index]

        def release(self):
            self.released = True

    def detect(image):
        predicted.append(image)
        return SimpleNamespace(face_landmarks=[])

    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(
            VideoCapture=Capture,
            CAP_PROP_POS_MSEC=1,
            COLOR_BGR2RGB=2,
            cvtColor=lambda frame, _: frame,
        ),
    )
    reader = FaceObservationReader()
    reader._task = SimpleNamespace(detect=detect)
    reader._mp = SimpleNamespace(
        Image=lambda **kwargs: kwargs["data"], ImageFormat=SimpleNamespace(SRGB=1)
    )
    return reader, video, captures, predicted


def test_reader_uses_decoder_timestamps_and_reuses_stateless_model(monkeypatch, tmp_path):
    reader, video, captures, predicted = fake_reader(
        monkeypatch, tmp_path, [0, 80, 100, 170, 200, 310]
    )
    for _ in range(2):
        rows = reader.extract(video, start_ms=0, end_ms=200)
        assert [row.at_ms for row in rows] == [0, 100, 200]
        assert all(row.face_count == 0 and row.gaze_x is None for row in rows)
    assert len(predicted) == 6 and all(cap.released for cap in captures)


@pytest.mark.parametrize("times", [[0, 0], [0, 100, 50], [float("nan")], [1000], [-1]])
def test_invalid_timing_never_falls_back_to_fps(monkeypatch, tmp_path, times):
    reader, video, captures, _ = fake_reader(monkeypatch, tmp_path, times)
    with pytest.raises(LandmarkError):
        reader.extract(video, start_ms=0, end_ms=2000)
    assert all(cap.released for cap in captures)


def test_large_frames_rejected_and_capture_released(monkeypatch, tmp_path):
    reader, video, captures, predicted = fake_reader(
        monkeypatch, tmp_path, [0], shape=(1081, 1920, 3)
    )
    with pytest.raises(LandmarkError) as error:
        reader.extract(video, start_ms=0, end_ms=100)
    assert error.value.status == Status.DEGRADED and not predicted
    assert captures[0].released


def test_playlist_or_non_video_bytes_rejected_before_loading_model(tmp_path):
    video = tmp_path / "fake.webm"
    video.write_text("#EXTM3U\nhttp://example.invalid/remote", encoding="utf-8")
    reader = FaceObservationReader()
    with pytest.raises(LandmarkError) as error:
        reader.extract(video, start_ms=0, end_ms=100)
    assert error.value.code == ErrorCode.E_DECODE
    assert reader._task is None


def test_failed_preload_is_not_silently_retried(tmp_path):
    path = tmp_path / "missing.task"
    reader = FaceObservationReader(model_path=path, expected_sha256="0" * 64)
    with pytest.raises(FileNotFoundError):
        reader.preload()
    path.write_bytes(b"now present")
    with pytest.raises(LandmarkError):
        reader.preload()


def test_modified_weights_are_rejected_before_importing_mediapipe(tmp_path):
    path = tmp_path / "model.task"
    path.write_bytes(b"modified model bytes")
    reader = FaceObservationReader(model_path=path, expected_sha256="0" * 64)
    with pytest.raises(LandmarkError) as error:
        reader.preload()
    assert error.value.code == ErrorCode.E_INTEGRITY
