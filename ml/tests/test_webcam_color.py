"""Host-clock color experiment tests: synthetic numbers/fake camera only."""

import json
import queue
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.eval.webcam_color import (
    MAX_DRAWS,
    MAX_ROWS,
    WebcamColorTrial,
    local_color_plan,
    observe_live,
)
from vericlue_ml.presence.chromapulse import log_linear
from vericlue_ml.presence.color_regions import ColorObservation, RegionStat


def trial_with_signal():
    plan, tail = local_color_plan()
    trial = WebcamColorTrial(10.0, plan, tail)
    names = ("forehead", "left_cheek", "right_cheek", "nose", "chin")
    for elapsed in np.arange(0, trial.duration_ms, 100):
        x = log_linear(plan.rgb_at(np.array([elapsed - 100])))[0]
        linear = np.exp(log_linear(np.array([115, 120, 125])) + x * 0.08)
        rgb = tuple((1.055 * linear ** (1 / 2.4) - 0.055) * 255)
        regions = {name: RegionStat(rgb, rgb, 100, 0.0) for name in names}
        regions["background"] = RegionStat((100, 100, 100), (100, 100, 100), 100, 0)
        trial.add(10 + elapsed / 1000, ColorObservation(0, 1, regions))
    for elapsed in range(0, trial.duration_ms + 200, 33):
        trial.record_draw(elapsed, trial.color_at(elapsed))
    return trial


def test_shared_plan_covers_palette_smoothly_and_has_bounded_duration():
    plan, tail = local_color_plan()
    assert len(set(plan.colors)) == 4 and all(
        a != b for a, b in zip(plan.colors, plan.colors[1:], strict=False)
    )
    assert 5900 <= plan.ends[-1] + tail <= 7900
    assert len(plan.config_sha256) == 64
    trial = WebcamColorTrial(0, plan, tail)
    assert trial.color_at(0) == plan.baseline
    assert trial.color_at(plan.starts[0]) == plan.baseline
    assert trial.color_at(plan.starts[0] + plan.transition_ms) == plan.colors[0]
    assert trial.color_at(plan.ends[-1]) == plan.colors[-1]
    assert trial.color_at(trial.duration_ms) == plan.baseline


@pytest.mark.parametrize("kind", ["fast", "red", "contrast", "long", "boolean"])
def test_unsupported_display_configuration_cannot_start(monkeypatch, tmp_path, kind):
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "packages/contracts/chromapulse.json"
    config = json.loads(source.read_text(encoding="utf-8"))
    if kind == "fast":
        config["hold_ms"] = {"min": 1, "max": 2}
        config["transition_ms"] = 1
    elif kind == "red":
        config["palette"][0] = "#ff0000"
    elif kind == "contrast":
        config["baseline_color"] = "#000000"
    elif kind == "long":
        config["hold_ms"]["max"] = 10000
    else:
        config["transition_ms"] = True
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("CHROMAPULSE_CONFIG", str(path))
    with pytest.raises(ValueError):
        local_color_plan()


def test_synthetic_fit_remains_degraded_with_local_clock_provenance():
    trial = trial_with_signal()
    result = trial.evaluate()
    assert result.status == "degraded" and result.gate == "unclear"
    assert result.score is None and result.prob_attack is None and not result.is_usable
    # The host seconds round-trip can cross a half-integer sRGB rounding edge.
    assert result.quality["fit_r2_in_sample"] > 0.999
    assert result.quality["apparent_lag_ms"] == 100
    assert result.quality["timing_verified"] is False
    assert result.quality["challenge_source"] == "local_lab_not_server_authenticated"
    assert result.model_version.endswith("+local-host-clock-v1")


@pytest.mark.parametrize("kind", ["missing", "gap", "late_start", "early_end"])
def test_incomplete_draw_schedule_does_not_publish_a_fit(kind):
    trial = trial_with_signal()
    if kind == "missing":
        trial.draws = []
    elif kind == "gap":
        trial.draws = [row for row in trial.draws if not 2000 < row["at_ms"] < 2600]
    elif kind == "late_start":
        trial.draws = trial.draws[10:]
    else:
        trial.draws = trial.draws[:50]
    result = trial.evaluate()
    assert "fit_r2_in_sample" not in result.quality
    assert result.gate == "unclear" and result.evidence[0].value == "display_schedule_interrupted"


def test_host_timestamps_and_memory_bounds_are_preserved_without_pixels():
    plan, tail = local_color_plan()
    trial = WebcamColorTrial(10.0, plan, tail)
    row = ColorObservation(999999, 0)
    for acquired in (9, float("nan"), 11, 11, 10.5, 100):
        trial.add(acquired, row)
    assert [r.at_ms for r in trial.observations] == [1000]
    for index in range(10000):
        trial.add(11 + index / 10000, row)
        trial.record_draw(index / 100, (209, 209, 209))
    assert len(trial.observations) == MAX_ROWS and len(trial.draws) == MAX_DRAWS
    assert not hasattr(trial, "frames")
    trial.add(12, None)


def test_eye_pose_and_color_share_one_landmark_call():
    calls = []

    class Reader:
        def measure(self, frame, *, at_ms, transform):
            calls.append(frame)
            return transform(SimpleNamespace(face_landmarks=[]), frame[:, :, ::-1])

    frame = np.full((100, 100, 3), 100, np.uint8)
    face, color = observe_live(Reader(), frame, with_color=True)
    assert len(calls) == 1 and face.face_count == color.face_count == 0
    assert observe_live(Reader(), frame, with_color=False)[1] is None


def fake_lab():
    from vericlue_ml.eval.webcam_lab import WebcamLab

    lab = object.__new__(WebcamLab)
    lab.generation = 7
    lab.color_busy = False
    lab.color_trial = None
    lab.color_result = None
    lab.color_plan = None
    lab.color_collect = threading.Event()
    lab.events = queue.SimpleQueue()
    lab.restored = False
    lab.restore_color_controls = lambda: setattr(lab, "restored", True)
    lab.render_results = lambda: None
    lab.status = SimpleNamespace(set=lambda text: None)
    return lab


def test_color_result_cannot_reappear_after_stop_or_new_generation():
    lab = fake_lab()
    lab.color_busy = True
    lab.receive_color_result(6, ({"old": True}, {}))
    assert not lab.color_busy and lab.color_result is None and not lab.restored
    lab.receive_color_result(7, ({"new": True}, {}))
    assert lab.color_result == {"new": True} and lab.restored


def test_cancel_clears_collection_and_does_not_evaluate_or_keep_old_trial():
    lab = fake_lab()
    lab.color_trial = trial_with_signal()
    lab.color_collect.set()
    lab.cancel_color_trial("cancelled")
    assert lab.color_trial is None and not lab.color_collect.is_set() and lab.restored
    assert lab.events.empty() and lab.color_result is None


def test_color_evaluation_error_stays_unavailable(monkeypatch):
    lab = fake_lab()

    def fail():
        raise RuntimeError("private exception")

    lab.score_color(7, SimpleNamespace(evaluate=fail))
    assert lab.events.get() == ("color_result", 7, (None, None))


def test_focus_loss_cancels_active_color_collection():
    lab = fake_lab()
    lab.closed = False
    lab.color_trial = trial_with_signal()
    lab.color_collect.set()
    lab.root = SimpleNamespace(focus_displayof=lambda: None)
    lab.check_color_visibility()
    assert lab.color_trial is None and not lab.color_collect.is_set()


def test_stop_clears_color_numbers_and_invalidates_pending_result():
    lab = fake_lab()
    widget = SimpleNamespace(configure=lambda **kwargs: None)
    lab.ai_button = lab.ref_button = lab.trial_button = lab.color_button = widget
    lab.target = lab.video = widget
    lab.root = SimpleNamespace(resizable=lambda *args: None)
    lab.stop_event = threading.Event()
    lab.lock = threading.Lock()
    lab.epoch = 0
    lab.color_trial = trial_with_signal()
    lab.color_collect.set()
    lab.color_result = {"stale": True}
    lab.stop_camera()
    assert lab.stop_event.is_set() and not lab.color_collect.is_set()
    assert lab.color_trial is None and lab.color_result is None and lab.color_plan is None
    lab.receive_color_result(7, ({"stale": True}, {}))
    assert lab.color_result is None


def test_color_report_exports_numbers_and_clock_provenance_only(monkeypatch, tmp_path):
    from vericlue_ml.eval import webcam_lab

    lab = fake_lab()
    trial = trial_with_signal()
    lab.score_color(7, trial)
    kind, token, payload = lab.events.get()
    assert kind == "color_result"
    lab.receive_color_result(token, payload)
    lab.results, lab.motion, lab.score_source = {}, {}, {}
    lab.motion_plan = None
    lab.landmarker_sha = "synthetic-unit-test"
    monkeypatch.setattr(webcam_lab, "ROOT", tmp_path)
    monkeypatch.setattr(webcam_lab, "runtime_versions", lambda: {"purpose": "synthetic_unit_test"})
    lab.save_report()
    paths = list((tmp_path / "tmp/webcam-lab").iterdir())
    assert len(paths) == 1 and paths[0].suffix == ".json"
    body = json.loads(paths[0].read_text(encoding="utf-8"))
    assert body["color"]["status"] == "degraded" and body["sample_count"] == 1
    assert body["color_plan"]["timestamp_source"].endswith("not_attested")
    assert body["color_plan"]["draw_requests"]
    assert not any(key in str(body) for key in ("embedding", "pixels", "face_landmarks"))
