"""Local webcam trial on synthetic trajectories; never open a physical camera."""

import queue
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.eval.webcam_trial import WebcamTrial
from vericlue_ml.presence.landmarks import FaceObservation


def test_live_trial_matches_both_windows_and_selects_actual_pixels():
    trial = WebcamTrial(10.0, order=("left", "right", "center"))
    plan = trial.gaze_plan
    points = np.asarray(plan.points)
    for t in range(0, 18201, 100):
        yaw = 28.0 if 12500 <= t < 14000 else -28.0 if 14500 <= t < 16000 else 0.0
        row = FaceObservation(
            0,
            1,
            0.5 + 0.2 * float(np.interp(t - 150, plan.times, points[:, 0])),
            0.2 * float(np.interp(t - 150, plan.times, points[:, 1])),
            yaw,
            0.0,
            0.0,
        )
        trial.add(10 + t / 1000, np.full((112, 112, 3), t // 100 % 255, np.uint8), row)
    gaze, head = trial.evaluate()
    assert gaze.gate == head.gate == "pass"
    frames = trial.selected_frames(head.view_times_ms)
    assert set(frames) == {"front", "left", "right"}
    assert len(trial.frames) <= 75 and len(trial.observations) <= 240
    assert frames["front"][0, 0, 0] == 10


def test_wrong_order_missing_gaze_or_bad_pose_never_passes():
    trial = WebcamTrial(0)
    assert all(result.gate != "pass" for result in trial.evaluate())
    with pytest.raises(ValueError):
        trial.selected_frames({"front": 1000, "left": 13200, "right": 15200})
    row = FaceObservation(0, 1, yaw_deg=28.0, pitch_deg=0.0, roll_deg=0.0)
    trial.frames = [(1000, np.zeros((10, 10, 3), np.uint8), row)]
    with pytest.raises(ValueError):
        trial.selected_frames({"front": 1000, "left": 13200, "right": 15200})


def test_capture_clock_order_bounds_and_copy_are_enforced():
    trial = WebcamTrial(10.0)
    frame = np.full((10, 10, 3), 7, np.uint8)
    row = FaceObservation(0, 1)
    for acquired in (9.0, float("nan"), 11.0, 11.0, 10.5, 100.0):
        trial.add(acquired, frame, row)
    assert len(trial.observations) == len(trial.frames) == 1
    frame[:] = 0
    assert trial.frames[0][1][0, 0, 0] == 7


def test_instructions_cover_dot_then_subject_left_right_without_auto_flip():
    trial = WebcamTrial(0, order=("right", "left", "center"))
    assert trial.cue(1000)[1] is None
    assert all(0.1 <= p <= 0.9 for p in trial.cue(7500)[1])
    assert "phải" in trial.cue(12500)[0] and "trái" in trial.cue(14500)[0]
    assert "giữa" in trial.cue(16500)[0]


def test_scheduled_snapshot_cannot_restart_after_stop_or_during_trial():
    from vericlue_ml.eval.webcam_lab import WebcamLab

    lab = object.__new__(WebcamLab)
    lab.closed = False
    lab.busy = False
    lab.auto_ai = False
    lab.trial = None
    lab.reference = np.zeros((10, 10, 3), np.uint8)
    lab.current = lambda: (0, 1.0, np.zeros((10, 10, 3), np.uint8), None)
    lab.submit = lambda frames: pytest.fail("stopped work must not restart")
    lab.submit_snapshot()
    lab.auto_ai = True
    lab.trial = WebcamTrial(0)
    lab.submit_snapshot()


def test_score_runs_real_interface_modes_and_keeps_frame_hashes_only():
    from vericlue_ml.common.result import Module, ModuleResult, Status
    from vericlue_ml.eval.webcam_lab import WebcamLab

    calls = []

    def detector(name):
        def measured(kind, kwargs):
            calls.append((name, kind, kwargs))
            return ModuleResult(
                module=Module(name),
                model_version="synthetic@unit",
                status=Status.OK,
                score=0.2,
                latency_ms=0,
            )

        return SimpleNamespace(
            name=name,
            preload=lambda **kwargs: None,
            predict_frame=lambda *args, **kwargs: measured("single", kwargs),
            predict_frames=lambda *args, **kwargs: measured("views", kwargs),
        )

    lab = object.__new__(WebcamLab)
    lab.models = tuple(detector(n) for n in ("face_match", "face_deepfake", "face_pad"))
    lab.models_dir = None
    lab.events = queue.SimpleQueue()
    frame = np.zeros((10, 10, 3), np.uint8)
    lab.score(7, frame, {"front": frame})
    assert [kind for _, kind, _ in calls] == ["views", "single", "single"]
    assert calls[0][2]["reference_frame"] is frame
    event = None
    while not lab.events.empty():
        event = lab.events.get()
    assert event[0] == "scores" and event[1] == 7
    results, source = event[2]
    assert len(source["reference_sha256"]) == 64 and source["mode"] == "single_frame"
    assert set(results) == {"face_match", "face_deepfake", "face_pad"}


def test_camera_failure_releases_owned_capture_and_reader(monkeypatch):
    import sys
    import threading

    from vericlue_ml.eval import webcam_lab

    released = []
    stop = threading.Event()

    class Capture:
        def set(self, *args):
            pass

        def isOpened(self):
            return True

        def read(self):
            return False, None

        def release(self):
            released.append("camera")

    class Reader:
        expected_sha256 = "a" * 64

        def preload(self, **kwargs):
            pass

        def close(self):
            released.append("reader")

    fakecv = SimpleNamespace(
        VideoCapture=lambda index: Capture(),
        CAP_PROP_FRAME_WIDTH=1,
        CAP_PROP_FRAME_HEIGHT=2,
        CAP_PROP_BUFFERSIZE=3,
    )
    monkeypatch.setitem(sys.modules, "cv2", fakecv)
    monkeypatch.setattr(webcam_lab, "FaceObservationReader", Reader)
    lab = object.__new__(webcam_lab.WebcamLab)
    lab.models_dir = None
    lab.camera = 0
    lab.events = queue.SimpleQueue()
    lab.lock = threading.Lock()
    lab.latest = None
    lab.camera_loop(3, stop)
    assert released == ["camera", "reader"]
    kinds = []
    while not lab.events.empty():
        kinds.append(lab.events.get()[0])
    assert kinds == ["camera_ready", "camera_error", "camera_stopped"]


def test_model_preload_error_is_sanitized_module_result():
    from vericlue_ml.common.result import ErrorCode
    from vericlue_ml.eval.webcam_lab import WebcamLab
    from vericlue_ml.face.pad import PadError

    def fail(**kwargs):
        raise PadError("private/model/location", ErrorCode.E_INTEGRITY)

    lab = object.__new__(WebcamLab)
    lab.models = (SimpleNamespace(name="face_pad", version="synthetic@unit", preload=fail),)
    lab.models_dir = None
    lab.events = queue.SimpleQueue()
    frame = np.zeros((10, 10, 3), np.uint8)
    lab.score(1, frame, {"front": frame})
    event = None
    while not lab.events.empty():
        event = lab.events.get()
    result = event[2][0]["face_pad"]
    assert result["status"] == "error" and result["error_code"] == "E_INTEGRITY"
    assert result["model_version"] == "synthetic@unit" and "private" not in str(result)
