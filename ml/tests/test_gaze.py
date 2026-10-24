"""Behavioral tests for provisional gaze rules; no weights, GPU or biometric fixtures."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Gate, Status
from vericlue_ml.presence.gaze import GazeDetector, evaluate_gaze, parse_plan
from vericlue_ml.presence.landmarks import FaceObservation, LandmarkError, eye_position, pose_angles

TARGET = [
    (0.5, 0.5),
    (0.2, 0.7),
    (0.8, 0.3),
    (0.3, 0.2),
    (0.7, 0.8),
    (0.2, 0.4),
    (0.6, 0.2),
    (0.8, 0.7),
]


def inputs():
    return DetectorInput(
        session_id="ses_test",
        video=Path("unused.webm"),
        metadata={
            "challenge_id": "ch_expected",
            "expected_challenge": {
                "challenge_id": "ch_expected",
                "dynamic": {
                    "version": 1,
                    "session_id": "ses_test",
                    "gaze_points": [
                        {"x": x, "y": y, "at_ms": 5000 + i * 1000}
                        for i, (x, y) in enumerate(TARGET)
                    ],
                },
            },
        },
    )


def matching(lag=150):
    plan = parse_plan(inputs())
    target = np.asarray(TARGET)
    return [
        FaceObservation(
            float(time),
            1,
            0.5 + 0.2 * float(np.interp(time - lag, plan.times, target[:, 0])),
            0.2 * float(np.interp(time - lag, plan.times, target[:, 1])),
            0.0,
            0.0,
            0.0,
        )
        for time in range(5000, 12001, 100)
    ]


def test_matching_trajectory_recovers_small_positive_lag():
    result = evaluate_gaze(matching(), parse_plan(inputs()))
    assert result.status == Status.OK and result.gate == Gate.PASS
    assert result.metrics["lag_ms"] == 150
    assert result.metrics["correlation_x"] > 0.99
    assert result.metrics["correlation_y"] > 0.99


@pytest.mark.parametrize("kind", ["still", "inverted", "different_path", "very_late"])
def test_observable_mismatch_fails(kind):
    rows = matching()
    if kind == "still":
        rows = [replace(row, gaze_x=0.5, gaze_y=0.1) for row in rows]
    elif kind == "inverted":
        rows = [replace(row, gaze_x=1 - row.gaze_x) for row in rows]
    elif kind == "different_path":
        random = np.random.default_rng(48)
        rows = [
            replace(row, gaze_x=float(random.random()), gaze_y=float(random.random()))
            for row in rows
        ]
    else:
        rows = matching(lag=1500)
    result = evaluate_gaze(rows, parse_plan(inputs()))
    assert result.status == Status.OK and result.gate == Gate.FAIL


@pytest.mark.parametrize(
    "kind",
    [
        "too_short",
        "missing_middle",
        "blink_long",
        "nonfinite",
        "duplicate_time",
        "reverse_time",
        "head_motion",
        "head_turned",
    ],
)
def test_unusable_evidence_cannot_pass(kind):
    rows = matching()
    if kind == "too_short":
        rows = rows[20:]
    elif kind == "missing_middle":
        rows = rows[:30] + rows[35:]
    elif kind == "blink_long":
        rows = [
            replace(row, gaze_x=None, gaze_y=None) if i % 2 else row for i, row in enumerate(rows)
        ]
    elif kind == "nonfinite":
        rows = [replace(row, gaze_x=float("nan")) for row in rows]
    elif kind == "duplicate_time":
        rows[10] = replace(rows[10], at_ms=rows[9].at_ms)
    elif kind == "reverse_time":
        rows = list(reversed(rows))
    elif kind == "head_motion":
        rows = [replace(row, yaw_deg=30.0 if i < 20 else 0.0) for i, row in enumerate(rows)]
    else:
        rows = [replace(row, yaw_deg=35.0) for row in rows]
    result = evaluate_gaze(rows, parse_plan(inputs()))
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR


def test_short_blink_is_tolerated_but_multiple_faces_are_not():
    rows = matching()
    rows[30] = replace(rows[30], gaze_x=None, gaze_y=None)
    assert evaluate_gaze(rows, parse_plan(inputs())).gate == Gate.PASS
    rows[30] = replace(rows[30], face_count=2)
    assert evaluate_gaze(rows, parse_plan(inputs())).status == Status.NOT_APPLICABLE
    assert (
        evaluate_gaze([FaceObservation(row.at_ms, 0) for row in rows], parse_plan(inputs())).status
        == Status.NOT_APPLICABLE
    )


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "other_session",
        "old_challenge",
        "bool_version",
        "nan_point",
        "bool_time",
        "reverse_times",
        "stationary_target",
    ],
)
def test_bad_or_unbound_server_plan_is_rejected(kind):
    inp = inputs()
    challenge = inp.metadata["expected_challenge"]
    dynamic = challenge["dynamic"]
    if kind == "missing":
        del inp.metadata["expected_challenge"]
    elif kind == "other_session":
        dynamic["session_id"] = "ses_other"
    elif kind == "old_challenge":
        inp.metadata["challenge_id"] = "ch_old"
    elif kind == "bool_version":
        dynamic["version"] = True
    elif kind == "nan_point":
        dynamic["gaze_points"][0]["x"] = float("nan")
    elif kind == "bool_time":
        dynamic["gaze_points"][0]["at_ms"] = True
    elif kind == "reverse_times":
        dynamic["gaze_points"].reverse()
    else:
        for row in dynamic["gaze_points"]:
            row["x"] = 0.5
    with pytest.raises(LandmarkError):
        parse_plan(inp)


class FakeReader:
    def __init__(self):
        self.calls = []

    def extract(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return matching()


def test_detector_reads_video_and_ignores_client_claimed_measurements():
    reader = FakeReader()
    inp = inputs()
    inp.signals = {"gaze": {"gate": "fail", "correlation": -1}}
    result = GazeDetector(reader).predict(inp)
    assert result.gate == Gate.PASS and result.prob_attack is None
    assert result.quality["provisional"] is True
    assert reader.calls == [(inp.video, {"start_ms": 5000.0, "end_ms": 12000.0})]
    inp.video = None
    inp.signals = {"gaze": {"gate": "pass", "correlation": 1}}
    assert GazeDetector(reader).predict(inp).status == Status.DEGRADED
    assert len(reader.calls) == 1


def test_detector_exceptions_never_turn_into_success():
    class BrokenReader:
        def extract(self, *args, **kwargs):
            raise RuntimeError("internal path or backend details")

    result = GazeDetector(BrokenReader()).predict(inputs())
    assert result.status == Status.ERROR and result.gate == Gate.UNCLEAR
    assert "internal path" not in result.model_dump_json()


def mesh():
    points = np.zeros((478, 3))
    for corners, lids, ring, x in [
        ((33, 133), (159, 145), (469, 470, 471, 472), 0.3),
        ((362, 263), (386, 374), (474, 475, 476, 477), 0.6),
    ]:
        points[corners[0], :2] = (x, 0.45)
        points[corners[1], :2] = (x + 0.1, 0.45)
        points[lids[0], :2] = (x + 0.05, 0.43)
        points[lids[1], :2] = (x + 0.05, 0.47)
        points[list(ring), :2] = (x + 0.05, 0.45)
    return points


def test_iris_geometry_normalizes_face_translation_and_rejects_closed_eyes():
    points = mesh()
    assert eye_position(points, 640, 480) == pytest.approx((0.5, 0.0))
    shifted = points.copy()
    shifted[:, :2] += 0.1
    assert eye_position(shifted, 640, 480) == pytest.approx((0.5, 0.0))
    points[list(range(469, 473)) + list(range(474, 478)), 0] += 0.02
    assert eye_position(points, 640, 480)[0] < 0.5
    points[159] = points[145]
    assert eye_position(points, 640, 480) is None


def test_pose_transform_yaw_is_only_an_estimate_and_rejects_bad_matrices():
    angle = np.deg2rad(25)
    matrix = np.eye(4)
    matrix[:3, :3] = [
        [np.cos(angle), 0, np.sin(angle)],
        [0, 1, 0],
        [-np.sin(angle), 0, np.cos(angle)],
    ]
    assert pose_angles(matrix) == pytest.approx((25, 0, 0))
    matrix[:3, :3] *= 2
    assert pose_angles(matrix) == pytest.approx((25, 0, 0))
    assert pose_angles(np.zeros((4, 4))) is None
    assert pose_angles(np.full((4, 4), np.nan)) is None
