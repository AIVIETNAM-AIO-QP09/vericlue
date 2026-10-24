"""Motion rules only: these synthetic traces do not test planar/deepfake resistance."""

from dataclasses import replace
from pathlib import Path

import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Gate, Status
from vericlue_ml.presence.head_turn import HeadTurnDetector, evaluate_head_turn, parse_head_plan
from vericlue_ml.presence.landmarks import FaceObservation, LandmarkError


def inputs(order=None):
    return DetectorInput(
        session_id="ses_head",
        video=Path("unused.mp4"),
        metadata={
            "challenge_id": "ch_head",
            "expected_challenge": {
                "challenge_id": "ch_head",
                "dynamic": {
                    "version": 1,
                    "session_id": "ses_head",
                    "head_start_at_ms": 12000,
                    "head_duration_ms": 6000,
                    "head_turns": order or ["left", "right", "center"],
                    "frontal_capture_at_ms": 1000,
                },
            },
        },
    )


def motion(reverse=False):
    rows = []
    for time in range(11500, 18001, 100):
        yaw = 0.0
        if 12500 <= time < 14000:
            yaw = 28.0
        elif 14500 <= time < 16000:
            yaw = -28.0
        rows.append(
            FaceObservation(
                float(time), 1, yaw_deg=-yaw if reverse else yaw, pitch_deg=0.0, roll_deg=0.0
            )
        )
    return rows


@pytest.mark.parametrize("reverse", [False, True])
def test_motion_requires_server_order_and_returns_view_times(reverse):
    inp = inputs(["right", "left", "center"] if reverse else None)
    result = evaluate_head_turn(motion(reverse), parse_head_plan(inp))
    assert result.status == Status.OK and result.gate == Gate.PASS
    assert result.reason == "motion_matched_depth_unverified"
    assert set(result.view_times_ms) == {"front", "left", "right"}
    assert result.view_times_ms["front"] == 1000
    assert (
        result.view_times_ms[inp.metadata["expected_challenge"]["dynamic"]["head_turns"][0]] < 14000
    )


@pytest.mark.parametrize(
    "kind", ["wrong_order", "no_motion", "only_first", "late", "spike", "return_again"]
)
def test_incorrect_or_incomplete_motion_fails(kind):
    rows = motion(reverse=kind == "wrong_order")
    if kind in {"no_motion", "late", "spike"}:
        rows = [replace(row, yaw_deg=0.0) for row in rows]
        if kind == "spike":
            rows[20] = replace(rows[20], yaw_deg=28.0)
            rows[40] = replace(rows[40], yaw_deg=-28.0)
    elif kind == "only_first":
        rows = [replace(row, yaw_deg=0.0) if row.yaw_deg < 0 else row for row in rows]
    elif kind == "return_again":
        rows = [replace(row, yaw_deg=28.0) if row.at_ms > 17000 else row for row in rows]
    if kind == "late":
        rows += [replace(row, at_ms=row.at_ms + 7000) for row in motion() if row.at_ms >= 12000]
    result = evaluate_head_turn(rows, parse_head_plan(inputs()))
    assert result.status == Status.OK and result.gate == Gate.FAIL


@pytest.mark.parametrize(
    "kind", ["short", "gap", "nan", "missing_pose", "duplicate_time", "tilt", "no_baseline"]
)
def test_unusable_video_evidence_never_passes(kind):
    rows = motion()
    if kind == "short":
        rows = rows[:-10]
    elif kind == "gap":
        rows = rows[:30] + rows[34:]
    elif kind == "nan":
        rows[10] = replace(rows[10], at_ms=float("nan"))
    elif kind == "missing_pose":
        rows = [replace(row, yaw_deg=None) for row in rows]
    elif kind == "duplicate_time":
        rows[10] = replace(rows[10], at_ms=rows[9].at_ms)
    elif kind == "tilt":
        rows[20] = replace(rows[20], pitch_deg=30.0)
    else:
        rows = [replace(row, yaw_deg=28.0) if row.at_ms < 12000 else row for row in rows]
    result = evaluate_head_turn(rows, parse_head_plan(inputs()))
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR


def test_no_face_and_multiple_faces_do_not_pass():
    plan = parse_head_plan(inputs())
    assert (
        evaluate_head_turn([FaceObservation(r.at_ms, 0) for r in motion()], plan).status
        == Status.NOT_APPLICABLE
    )
    rows = motion()
    rows[30] = replace(rows[30], face_count=2)
    assert evaluate_head_turn(rows, plan).status == Status.NOT_APPLICABLE


@pytest.mark.parametrize(
    "key,value",
    [
        ("session_id", "other_session"),
        ("version", True),
        ("head_start_at_ms", True),
        ("head_duration_ms", 8000),
        ("head_turns", ["left", "left", "center"]),
        ("frontal_capture_at_ms", 12000),
    ],
)
def test_invalid_or_unbound_plan_is_rejected(key, value):
    inp = inputs()
    inp.metadata["expected_challenge"]["dynamic"][key] = value
    with pytest.raises(LandmarkError):
        parse_head_plan(inp)


def test_detector_reads_server_bound_window_and_ignores_client_claims():
    class Reader:
        def extract(self, path, **kwargs):
            assert path == Path("unused.mp4")
            assert kwargs == {"start_ms": 11500.0, "end_ms": 18000.0}
            return motion()

    inp = inputs()
    inp.signals = {"head_turn": {"gate": "fail", "depth_verified": True}}
    result = HeadTurnDetector(Reader()).predict(inp)
    assert result.gate == Gate.PASS and result.prob_attack is None
    assert result.quality == {"provisional": True, "depth_verified": False}
    inp.video = None
    assert HeadTurnDetector(Reader()).predict(inp).status == Status.DEGRADED


def test_reader_errors_are_sanitized():
    class Reader:
        def extract(self, *args, **kwargs):
            raise RuntimeError("private path")

    result = HeadTurnDetector(Reader()).predict(inputs())
    assert result.status == Status.ERROR and result.gate == Gate.UNCLEAR
    assert "private path" not in result.model_dump_json()
