"""Combined face timing/lifecycle on synthetic frames only; no live devices or weights."""

import json
import queue
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.eval.presence_lab import PresenceLab
from vericlue_ml.eval.presence_trial import PresenceTrial
from vericlue_ml.eval.webcam_trial import WebcamTrial
from vericlue_ml.presence.chromapulse import log_linear
from vericlue_ml.presence.color_regions import ColorObservation, RegionStat
from vericlue_ml.presence.landmarks import FaceObservation


def synthetic_trial():
    trial = PresenceTrial.create(10.0)
    trial.motion.order = ("left", "right", "center")
    plan, head = trial.motion.gaze_plan, trial.motion.head_plan
    points = np.asarray(plan.points)
    for t in range(0, int(trial.duration_ms) + 201, 100):
        delta = t - head.start_ms
        yaw = 28.0 if 500 <= delta < 2000 else -28.0 if 2500 <= delta < 4000 else 0.0
        face = FaceObservation(
            0,
            1,
            0.5 + 0.2 * float(np.interp(t - 150, plan.times, points[:, 0])),
            0.2 * float(np.interp(t - 150, plan.times, points[:, 1])),
            yaw,
            0.0,
            0.0,
        )
        x = log_linear(trial.color.plan.rgb_at(np.array([t - 100])))[0]
        linear = np.exp(log_linear(np.array([115, 120, 125])) + x * 0.08)
        rgb = tuple((1.055 * linear ** (1 / 2.4) - 0.055) * 255)
        regions = {
            name: RegionStat(rgb, rgb, 100, 0.0)
            for name in ("forehead", "left_cheek", "right_cheek", "nose", "chin")
        }
        regions["background"] = RegionStat((100, 100, 100), (100, 100, 100), 100, 0)
        trial.add(
            10 + t / 1000,
            np.full((16, 16, 3), t // 100 % 255, np.uint8),
            face,
            ColorObservation(0, 1, regions),
        )
    for t in range(0, trial.color.duration_ms + 150, 33):
        trial.color.record_draw(t, trial.color.color_at(t))
    return trial


def test_combined_schedule_preserves_color_rules_and_shifts_motion_without_extra_capture():
    trial = synthetic_trial()
    assert 18900 <= trial.duration_ms <= 20900
    assert trial.motion.gaze_plan.times[0] == trial.color.duration_ms
    assert trial.motion.head_plan.start_ms == trial.color.duration_ms + 7000
    report, frames = trial.evaluate()
    assert set(frames) == {"front", "left", "right"}
    assert report["motion_plan"]["trial_id"] == report["color_plan"]["trial_id"]
    assert report["motion_plan"]["authentication_decision"] == "not_provided"
    assert all(value["gate"] == "pass" for value in report["motion"].values())
    assert report["color"]["status"] == "degraded" and report["color"]["gate"] == "unclear"
    assert report["color"]["quality"]["fit_r2_in_sample"] > 0.999
    assert frames["front"][0, 0, 0] == 10
    assert len(trial.motion.frames) <= 75 and len(trial.motion.observations) <= 240
    assert len(trial.color.observations) <= 120


def test_cues_and_pixels_keep_exact_boundaries_without_logging_unpainted_colors():
    trial = PresenceTrial.create(0)
    assert trial.cue(0)[0] == 1 and trial.cue(0)[2] is None
    assert trial.cue(trial.color.duration_ms - 1)[0] == 1
    step, text, dot, rgb = trial.cue(trial.color.duration_ms)
    assert step == 2 and dot is not None and rgb is None
    assert trial.cue(trial.motion.head_plan.start_ms)[0] == 3
    assert not trial.color.draws


@pytest.mark.parametrize("kind", ["color", "eyes", "head"])
def test_stage_failure_is_visible_without_erasing_other_stage_results(monkeypatch, kind):
    from vericlue_ml.eval import presence_trial

    trial = synthetic_trial()

    def fail(*_args):
        raise RuntimeError("PRIVATE_DETAILS")

    if kind == "color":
        trial.color.evaluate = fail
    else:
        monkeypatch.setattr(
            presence_trial, "evaluate_gaze" if kind == "eyes" else "evaluate_head_turn", fail
        )
    report, frames = trial.evaluate()
    assert "PRIVATE_DETAILS" not in json.dumps(report)
    if kind == "color":
        assert report["color"]["status"] == "error" and len(frames) == 3
        assert all(value["gate"] == "pass" for value in report["motion"].values())
    else:
        failed = "gaze_tracking" if kind == "eyes" else "head_turn"
        other = "head_turn" if kind == "eyes" else "gaze_tracking"
        assert report["motion"][failed]["status"] == "error"
        assert report["motion"][other]["gate"] == "pass" and not frames
        assert report["color"]["gate"] == "unclear"


@pytest.mark.parametrize("kind", ["missing_draws", "missing_motion", "missing_pixels"])
def test_missing_samples_do_not_turn_into_a_complete_measurement(kind):
    trial = synthetic_trial()
    if kind == "missing_draws":
        trial.color.draws.clear()
    elif kind == "missing_motion":
        trial.motion.observations.clear()
    else:
        trial.motion.frames.clear()
    report, frames = trial.evaluate()
    if kind == "missing_draws":
        assert "fit_r2_in_sample" not in report["color"]["quality"]
    else:
        assert not frames and not report["motion_plan"]["three_views_available"]


def test_wipe_removes_owned_pixels_without_changing_selected_copies():
    trial = synthetic_trial()
    owned = [frame for _, frame, _ in trial.motion.frames]
    _, selected = trial.evaluate()
    trial.wipe()
    assert all(not np.any(frame) for frame in owned)
    assert not trial.motion.frames and not trial.motion.observations
    assert not trial.color.observations and not trial.color.draws
    assert selected["front"][0, 0, 0] == 10


@pytest.mark.parametrize("start", [True, 4999, 10001, float("nan"), float("inf")])
def test_shifted_local_schedule_stays_bounded(start):
    with pytest.raises(ValueError):
        WebcamTrial(0, gaze_start_ms=start)


class Widget:
    def __init__(self):
        self.values = {}

    def configure(self, **kwargs):
        self.values.update(kwargs)


def fake_lab():
    lab = object.__new__(PresenceLab)
    lab.generation = 7
    lab.closed = lab.preview = lab.busy = lab.color_busy = False
    lab.presence_busy = False
    lab.presence_trial = lab.trial = lab.color_trial = None
    lab.presence_events = queue.SimpleQueue()
    lab.color_collect = threading.Event()
    lab.current = lambda: (0, 10.0, np.ones((16, 16, 3), np.uint8), FaceObservation(0, 1), None)
    lab.root = SimpleNamespace(resizable=lambda *_: None, focus_displayof=lambda: None)
    lab.status = SimpleNamespace(set=lambda text: setattr(lab, "message", text))
    lab.presence_button, lab.single_button = Widget(), Widget()
    lab.ref_button, lab.ai_button, lab.trial_button, lab.color_button = [Widget() for _ in range(4)]
    lab.reference = None
    lab.target = Widget()
    lab.restore_color_controls = lambda: setattr(lab, "restored", True)
    lab.clear_color_result = lambda: setattr(lab, "color_result", None)
    lab.render_results = lambda: None
    return lab


def test_one_action_starts_without_model_or_device_and_blocks_overlapping_actions(monkeypatch):
    from vericlue_ml.eval.webcam_lab import WebcamLab

    lab = fake_lab()
    lab.start_presence_trial()
    first = lab.presence_trial
    assert first is not None and lab.color_collect.is_set() and lab.generation == 8
    assert lab.presence_button.values["state"] == "disabled"
    for name in (
        "start_trial",
        "start_color_trial",
        "capture_reference",
        "toggle_ai",
        "submit_snapshot",
    ):
        monkeypatch.setattr(WebcamLab, name, lambda *_: pytest.fail("must not overlap"))
        getattr(lab, name)()
    lab.start_presence_trial()
    assert lab.presence_trial is first


@pytest.mark.parametrize("kind", ["preview", "no_camera", "multiple", "model_busy"])
def test_cannot_start_while_not_ready(kind):
    lab = fake_lab()
    if kind == "preview":
        lab.preview = True
    elif kind == "no_camera":
        lab.current = lambda: None
    elif kind == "multiple":
        lab.current = lambda: (0, 10.0, None, FaceObservation(0, 2), None)
    else:
        lab.busy = True
    lab.start_presence_trial()
    assert lab.presence_trial is None and not lab.color_collect.is_set()


@pytest.mark.parametrize("cause", ["cancel", "focus", "hide"])
def test_cancel_or_invisible_window_discards_trial_and_zeros_owned_pixels(cause):
    lab = fake_lab()
    trial = synthetic_trial()
    pixels = trial.motion.frames[0][1]
    lab.presence_trial = trial
    lab.color_collect.set()
    if cause == "focus":
        lab.check_color_visibility()
    elif cause == "hide":
        lab.cancel_color_trial("hidden")
    else:
        lab.cancel_presence_trial("cancelled")
    assert lab.presence_trial is None and not lab.color_collect.is_set()
    assert not pixels.any() and lab.color_result is None and lab.generation == 8


def test_late_worker_result_is_dropped_and_its_frames_wiped():
    lab = fake_lab()
    lab.presence_busy = True
    frame = np.ones((16, 16, 3), np.uint8)
    frames = {"front": frame}
    lab.receive_presence_result(6, {"private": "old"}, frames)
    assert not lab.presence_busy and not frames and not frame.any()
    assert not hasattr(lab, "motion") and lab.restored


def test_cancel_while_evaluating_waits_for_owned_job_then_drops_all_pixels():
    lab = fake_lab()
    trial = synthetic_trial()
    entered, release = threading.Event(), threading.Event()
    original = trial.evaluate

    def blocked():
        entered.set()
        assert release.wait(5)
        return original()

    trial.evaluate = blocked
    lab.presence_busy = True
    worker = threading.Thread(target=lab.score_presence, args=(7, trial))
    worker.start()
    assert entered.wait(5)
    try:
        lab.cancel_presence_trial("cancelled")
        assert lab.presence_busy and lab.presence_button.values["state"] != "normal"
    finally:
        release.set()
    worker.join(5)
    assert not worker.is_alive()
    token, report, frames = lab.presence_events.get_nowait()
    assert report is None and not frames and not trial.motion.frames
    lab.receive_presence_result(token, report, frames)
    assert not lab.presence_busy


def test_results_and_reports_keep_same_trial_without_retaining_frames():
    lab = fake_lab()
    trial = synthetic_trial()
    report, frames = trial.evaluate()
    pixels = list(frames.values())
    lab.presence_busy = True
    lab.receive_presence_result(7, report, frames)
    assert lab.motion_plan["trial_id"] == lab.color_plan["trial_id"]
    assert lab.color_result["gate"] == "unclear"
    assert not frames and all(not frame.any() for frame in pixels)


def test_combined_report_exports_shared_plan_and_metrics_only(monkeypatch, tmp_path):
    from vericlue_ml.eval import webcam_lab

    lab = fake_lab()
    report, frames = synthetic_trial().evaluate()
    lab.receive_presence_result(7, report, frames)
    lab.results, lab.score_source = {}, {}
    lab.landmarker_sha = "synthetic"
    monkeypatch.setattr(webcam_lab, "ROOT", tmp_path)
    monkeypatch.setattr(webcam_lab, "runtime_versions", lambda: {"purpose": "synthetic"})
    lab.save_report()
    path = next((tmp_path / "tmp/webcam-lab").iterdir())
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["plan"]["trial_id"] == body["color_plan"]["trial_id"]
    assert body["plan"]["authentication_decision"] == "not_provided"
    assert body["color"]["gate"] == "unclear" and body["sample_count"] == 1
    assert not any(key in str(body) for key in ("pixels", "embedding", "face_landmarks"))


def test_background_scorer_gets_pixels_before_owned_buffers_are_cleared(monkeypatch):
    from vericlue_ml.eval.webcam_lab import WebcamLab

    observed = []

    def score(_self, token, reference, frames):
        observed.append((token, reference.copy(), frames["front"].copy()))

    monkeypatch.setattr(WebcamLab, "score", score)
    lab = fake_lab()
    reference = np.ones((16, 16, 3), np.uint8)
    frame = np.full((16, 16, 3), 9, np.uint8)
    frames = {"front": frame}
    lab.score(7, reference, frames)
    assert observed[0][0] == 7 and observed[0][1].all() and (observed[0][2] == 9).all()
    assert not reference.any() and not frame.any() and not frames


@pytest.mark.slow
def test_native_reader_feeds_both_parts_on_one_synthetic_frame():
    import os
    from pathlib import Path

    root = os.getenv("GAZE_MODELS_DIR")
    if not root:
        pytest.skip("Set GAZE_MODELS_DIR in the isolated face runtime")
    from vericlue_ml.eval.webcam_color import observe_live
    from vericlue_ml.presence.landmarks import FaceObservationReader

    trial = PresenceTrial.create(10)
    reader = FaceObservationReader()
    try:
        reader.preload(models_dir=Path(root))
        task = reader._task
        frame = np.full((240, 320, 3), 110, np.uint8)
        face, color = observe_live(reader, frame, with_color=True)
        trial.add(11, frame, face, color)
        report, frames = trial.evaluate()
        assert reader._task is task and reader.expected_sha256
        assert trial.motion.observations[0].at_ms == trial.color.observations[0].at_ms == 1000
        assert all(value["gate"] != "pass" for value in report["motion"].values())
        assert report["color"]["gate"] == "unclear" and not frames
    finally:
        trial.wipe()
        reader.close()
