"""SyncNet selects VFR presentation times and fails closed on unreliable clocks."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Module, Status
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.router.policy import TrustRouter
from vericlue_ml.voice import syncnet

VFR_TIMES = [
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
]


@pytest.fixture
def fake_capture(monkeypatch):
    """Expose actual PTS while rejecting average-FPS lookup or frame-index seeking."""

    def install(timestamps, *, opened=True, crop_error=None):
        cv2 = ModuleType("cv2")
        cv2.CAP_PROP_POS_MSEC = 10
        capture = SimpleNamespace(released=False, position=-1, crops=[])

        def read():
            capture.position += 1
            if capture.position >= len(timestamps):
                return False, None
            return True, capture.position

        def get(prop):
            assert prop == cv2.CAP_PROP_POS_MSEC, "Use actual PTS, never average FPS"
            return timestamps[capture.position] * 1000

        def release():
            capture.released = True

        def crop(image, finder):
            if crop_error is not None:
                raise crop_error
            capture.crops.append(image)
            return image

        def seek(*args):
            raise AssertionError("VFR input must not seek using an average frame rate")

        capture.read, capture.get, capture.release = read, get, release
        capture.isOpened, capture.set = lambda: opened, seek
        cv2.VideoCapture = lambda path: capture
        monkeypatch.setitem(sys.modules, "cv2", cv2)
        monkeypatch.setattr(syncnet, "_face_crop", crop)
        return capture

    return install


def test_vfr_selects_nearest_actual_timestamps_preserves_order_and_releases(fake_capture):
    capture = fake_capture(VFR_TIMES)
    starts = [1, 0]
    windows = syncnet._read_windows(Path("unopened.webm"), starts, object())
    expected = [
        [
            min(range(len(VFR_TIMES)), key=lambda index: abs(VFR_TIMES[index] - position / 25))
            for position in range(start, start + 16)
        ]
        for start in starts
    ]
    assert windows == expected
    assert len(capture.crops) == len({index for window in expected for index in window})
    assert capture.released is True


@pytest.mark.parametrize(
    "bad_pts", [[float("nan")], [float("inf")], [-0.01], [0, 0], [0, 0.04, 0.03]]
)
def test_invalid_or_nonmonotonic_pts_degrades_result_and_reviews(fake_capture, bad_pts):
    capture = fake_capture(bad_pts)
    alignment = SimpleNamespace(
        splice_events=[],
        syllables=[],
        aligned_segments=[SimpleNamespace(start_s=0.0, end_s=4.0)],
    )
    aligner = SimpleNamespace(
        preload=lambda **kwargs: None,
        align=lambda audio, prompt: alignment,
    )
    backend = SimpleNamespace(preload=lambda **kwargs: None)
    detector = syncnet.SyncNetDetector(aligner=aligner, finder=object(), backend=backend)
    result = detector.predict(
        DetectorInput(
            video=Path("unopened.webm"), audio=Path("unopened.wav"), metadata={"prompt": "câu"}
        )
    )
    assert result.status == Status.DEGRADED
    assert result.error_code == ErrorCode.E_LOW_QUALITY
    assert result.score is result.prob_attack is None
    assert capture.released is True
    results = {
        module: MockDetector(module).predict(DetectorInput())
        for module in (Module.VOICE_CHALLENGE, Module.VOICE_SPOOF)
    }
    results[Module.LIPSYNC] = result
    assert TrustRouter(profile="mvp").voice(results).status == "review"


def test_frame_gap_larger_than_forty_ms_is_degraded(fake_capture):
    capture = fake_capture([0.0, 0.2, 0.4, 0.6])
    with pytest.raises(syncnet.SyncNetError) as caught:
        syncnet._read_windows(Path("unopened.webm"), [0], object())
    assert caught.value.status == "degraded"
    assert caught.value.code == ErrorCode.E_LOW_QUALITY
    assert capture.released is True


def test_eof_uses_last_frame_only_when_it_is_within_resampling_tolerance(fake_capture):
    timestamps = [i / 25 for i in range(15)] + [0.58]
    capture = fake_capture(timestamps)
    windows = syncnet._read_windows(Path("unopened.webm"), [0], object())
    assert len(windows[0]) == 16
    assert windows[0][-1] == len(timestamps) - 1
    assert capture.released is True


@pytest.mark.parametrize(
    "failure",
    [
        syncnet.SyncNetError("No face", ErrorCode.E_NO_FACE, "not_applicable"),
        syncnet.SyncNetError("Ambiguous face", ErrorCode.E_MULTI_FACE, "degraded"),
        syncnet.SyncNetError("Synthetic decoder error", ErrorCode.E_DECODE),
    ],
)
def test_face_and_decode_errors_propagate_without_leaking_capture(fake_capture, failure):
    capture = fake_capture(VFR_TIMES, crop_error=failure)
    with pytest.raises(syncnet.SyncNetError) as caught:
        syncnet._read_windows(Path("unopened.webm"), [0], object())
    assert caught.value is failure
    assert capture.released is True


@pytest.mark.parametrize("opened", [True, False])
def test_missing_or_unopenable_video_errors_and_releases(fake_capture, opened):
    capture = fake_capture([], opened=opened)
    with pytest.raises(syncnet.SyncNetError) as caught:
        syncnet._read_windows(Path("unopened.webm"), [0], object())
    assert caught.value.status == "error"
    assert caught.value.code == ErrorCode.E_DECODE
    assert capture.released is True


def test_frame_count_limit_stops_pathological_decoding(fake_capture, monkeypatch):
    capture = fake_capture([0.0, 0.01, 0.02, 0.03])
    monkeypatch.setattr(syncnet, "MAX_DECODE_FRAMES", 2)
    with pytest.raises(syncnet.SyncNetError, match="Too many video frames"):
        syncnet._read_windows(Path("unopened.webm"), [0], object())
    assert capture.released is True


def test_timestamp_past_maximum_duration_errors_and_releases(fake_capture):
    capture = fake_capture([121.0])
    with pytest.raises(syncnet.SyncNetError) as caught:
        syncnet._read_windows(Path("unopened.webm"), [0], object())
    assert caught.value.code == ErrorCode.E_DECODE
    assert capture.released is True
