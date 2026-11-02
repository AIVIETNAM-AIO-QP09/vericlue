"""FLOW-04 motion order/timing only; an estimated pose is not physical depth evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.head_protocol import head_protocol_version
from vericlue_ml.presence.landmarks import (
    MAX_VIDEO_MS,
    FaceObservation,
    FaceObservationReader,
    LandmarkError,
)

HEAD_VERSION = "head-turn-rules@0.2+face-landmarker-f16-1"
# Provisional motion/quality constants, not calibrated attack thresholds.
TURN_MIN_DEG = 20
TURN_MAX_DEG = 50
MAX_USABLE_YAW_DEG = 58
TARGET_TURN_DEG = 28.0
CENTER_MAX_DEG = 8
MAX_PITCH_ROLL_DEG = 15
MIN_HOLD_MS = 300
BASELINE_MS = 500
BASELINE_HOLD_MS = 200
MAX_GAP_MS = 300
MIN_COVERAGE = 0.8
EDGE_TOLERANCE_MS = 200


@dataclass(frozen=True)
class HeadPlan:
    start_ms: float
    end_ms: float
    order: tuple[str, ...]
    frontal_capture_at_ms: float
    adaptive: bool = False


def parse_head_plan(inp: DetectorInput) -> HeadPlan:
    head_protocol_version(inp)
    dynamic = expected_dynamic(inp)
    start, duration = dynamic.get("head_start_at_ms"), dynamic.get("head_duration_ms")
    frontal = dynamic.get("frontal_capture_at_ms")
    order = dynamic.get("head_turns")
    mode, timeout = dynamic.get("head_mode"), dynamic.get("head_timeout_ms")
    if (
        type(start) is not int
        or not BASELINE_MS <= start <= 24_000
        or type(duration) is not int
        or type(frontal) is not int
        or not 0 <= frontal < start - BASELINE_MS
        or order not in (["left", "right", "center"], ["right", "left", "center"])
        or mode not in (None, "adaptive")
        or (mode is None and timeout is not None)
        or (
            mode == "adaptive"
            and (type(timeout) is not int or not 6000 <= timeout <= MAX_VIDEO_MS - start)
        )
    ):
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    end = start + (timeout if mode == "adaptive" else duration)
    return HeadPlan(float(start), float(end), tuple(order), float(frontal), mode == "adaptive")


@dataclass(frozen=True)
class HeadEvaluation:
    status: Status
    gate: Gate
    reason: str
    view_times_ms: dict[str, float]


def direction(row: FaceObservation) -> str | None:
    """Subject-left is positive model yaw on unmirrored front video; validate on hardware."""
    if abs(row.yaw_deg) <= CENTER_MAX_DEG:
        return "center"
    if TURN_MIN_DEG <= row.yaw_deg <= TURN_MAX_DEG:
        return "left"
    if -TURN_MAX_DEG <= row.yaw_deg <= -TURN_MIN_DEG:
        return "right"
    return None


def evaluate_head_turn(rows: list[FaceObservation], plan: HeadPlan) -> HeadEvaluation:
    def result(status, gate, reason, times=None):
        return HeadEvaluation(status, gate, reason, times or {})

    if (
        not rows
        or any(not math.isfinite(row.at_ms) for row in rows)
        or any(a.at_ms >= b.at_ms for a, b in zip(rows, rows[1:], strict=False))
    ):
        return result(Status.DEGRADED, Gate.UNCLEAR, "missing_or_invalid_timestamps")
    window = [row for row in rows if plan.start_ms - BASELINE_MS <= row.at_ms <= plan.end_ms]
    if plan.adaptive and any(row.at_ms > plan.end_ms for row in rows):
        return result(Status.DEGRADED, Gate.UNCLEAR, "capture_deadline_exceeded")
    if any(row.face_count > 1 for row in window):
        return result(Status.NOT_APPLICABLE, Gate.UNCLEAR, "multiple_faces")
    if window and all(row.face_count == 0 for row in window):
        return result(Status.NOT_APPLICABLE, Gate.UNCLEAR, "no_face")
    valid = [
        row
        for row in window
        if row.face_count == 1
        and all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            for value in (row.yaw_deg, row.pitch_deg, row.roll_deg)
        )
    ]
    # Adaptive recordings end at decoder EOF, never at a client-claimed completion timestamp.
    observed_end = window[-1].at_ms if plan.adaptive and window else plan.end_ms
    expected = (observed_end - plan.start_ms + BASELINE_MS) / 100 + 1
    if len(valid) < 2 or expected <= 0 or len(valid) / expected < MIN_COVERAGE:
        return result(Status.DEGRADED, Gate.UNCLEAR, "insufficient_coverage")
    times = np.asarray([row.at_ms for row in valid])
    if (
        times[0] > plan.start_ms - BASELINE_MS + EDGE_TOLERANCE_MS
        or times[-1] < observed_end - EDGE_TOLERANCE_MS
        or np.diff(times).max() > MAX_GAP_MS
    ):
        return result(Status.DEGRADED, Gate.UNCLEAR, "incomplete_time_window")
    if not plan.adaptive and any(
        abs(row.pitch_deg) > MAX_PITCH_ROLL_DEG or abs(row.roll_deg) > MAX_PITCH_ROLL_DEG
        for row in valid
    ):
        return result(Status.DEGRADED, Gate.UNCLEAR, "pose_out_of_range")
    if not plan.adaptive:
        # A transient yaw overshoot is unusable evidence, not an automatic whole-video veto.
        # Keep the same coverage/gap/edge limits; prolonged overshoot still fails closed.
        usable = [row for row in valid if abs(row.yaw_deg) <= MAX_USABLE_YAW_DEG]
        usable_times = np.asarray([row.at_ms for row in usable])
        if (
            len(usable) / expected < MIN_COVERAGE
            or usable_times[0] > plan.start_ms - BASELINE_MS + EDGE_TOLERANCE_MS
            or usable_times[-1] < plan.end_ms - EDGE_TOLERANCE_MS
            or np.diff(usable_times).max() > MAX_GAP_MS
        ):
            return result(Status.DEGRADED, Gate.UNCLEAR, "pose_out_of_range")
    baseline = [row for row in valid if row.at_ms < plan.start_ms]
    if (
        not baseline
        or baseline[-1].at_ms - baseline[0].at_ms < BASELINE_HOLD_MS
        or any(direction(row) != "center" for row in baseline)
        or any(max(abs(row.pitch_deg), abs(row.roll_deg)) > MAX_PITCH_ROLL_DEG for row in baseline)
    ):
        return result(Status.DEGRADED, Gate.UNCLEAR, "neutral_baseline_missing")
    if plan.adaptive:
        return evaluate_adaptive_holds(window, plan)
    # Iterate all measured poses: out-of-range yaw maps to None and breaks a hold,
    # so filtering cannot join brief valid fragments into a sustained command.
    runs: list[tuple[str, float]] = []
    current: str | None = None
    run_rows: list[FaceObservation] = []

    def _pick_run_time(label: str, items: list[FaceObservation]) -> float:
        target = 0.0 if label == "center" else TARGET_TURN_DEG
        best = min(
            items,
            key=lambda r: (
                abs(abs(float(r.yaw_deg)) - target),
                abs(float(r.pitch_deg)) + abs(float(r.roll_deg)),
            ),
        )
        return float(best.at_ms)

    for row in [r for r in valid if r.at_ms >= plan.start_ms]:
        label = direction(row)
        if label != current or (run_rows and row.at_ms - run_rows[-1].at_ms > MAX_GAP_MS):
            if current is not None and run_rows[-1].at_ms - run_rows[0].at_ms >= MIN_HOLD_MS:
                runs.append((current, _pick_run_time(current, run_rows)))
            current = label
            run_rows = [row] if label is not None else []
        elif label is not None:
            run_rows.append(row)
    if current is not None and run_rows and run_rows[-1].at_ms - run_rows[0].at_ms >= MIN_HOLD_MS:
        runs.append((current, _pick_run_time(current, run_rows)))
    stage = 0
    view_times = {"front": plan.frontal_capture_at_ms}
    for label, at_ms in runs:
        if stage == 0 and label == "center":
            continue
        if stage == 1 and label in (plan.order[0], "center"):
            continue
        if stage == 2 and label == plan.order[1]:
            continue
        if stage == 3 and label == "center":
            continue
        if stage == 3 or label != plan.order[stage]:
            return result(Status.OK, Gate.FAIL, "wrong_order")
        if label != "center":
            view_times[label] = at_ms
        stage += 1
    if stage != 3:
        return result(Status.OK, Gate.FAIL, "motion_incomplete")
    return result(Status.OK, Gate.PASS, "motion_matched_depth_unverified", view_times)


def evaluate_adaptive_holds(rows: list[FaceObservation], plan: HeadPlan) -> HeadEvaluation:
    """Wait for each ordered hold; wrong or unusable poses reset only the current hold."""
    stage = 0
    hold_start = None
    last = None
    view_times = {"front": plan.frontal_capture_at_ms}
    for row in rows:
        if row.at_ms < plan.start_ms:
            continue
        usable = row.face_count == 1 and all(
            type(value) in (int, float) and math.isfinite(value)
            for value in (row.yaw_deg, row.pitch_deg, row.roll_deg)
        )
        usable = usable and (
            abs(row.pitch_deg) <= MAX_PITCH_ROLL_DEG
            and abs(row.roll_deg) <= MAX_PITCH_ROLL_DEG
            and abs(row.yaw_deg) <= TURN_MAX_DEG
        )
        label = direction(row) if usable else None
        # Completion still requires a sustained neutral tail at the actual media end.
        if stage == len(plan.order):
            if label == "center" and last is not None and row.at_ms - last <= MAX_GAP_MS:
                last = row.at_ms
                continue
            stage = len(plan.order) - 1
            hold_start = None
        if label != plan.order[stage] or (last is not None and row.at_ms - last > MAX_GAP_MS):
            hold_start = None
        if label == plan.order[stage]:
            if hold_start is None:
                hold_start = row.at_ms
            if row.at_ms - hold_start >= MIN_HOLD_MS:
                if label != "center":
                    view_times[label] = (hold_start + row.at_ms) / 2
                stage += 1
                hold_start = None
        last = row.at_ms
    if stage != len(plan.order):
        return HeadEvaluation(Status.OK, Gate.FAIL, "motion_incomplete", {})
    return HeadEvaluation(Status.OK, Gate.PASS, "motion_matched_depth_unverified", view_times)


class HeadTurnDetector:
    name = Module.HEAD_TURN.value
    version = HEAD_VERSION

    def __init__(self, reader: FaceObservationReader | None = None) -> None:
        self.reader = reader if reader is not None else FaceObservationReader()

    def preload(self, **kwargs) -> None:
        self.reader.preload(**kwargs)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = perf_counter()
        try:
            plan = parse_head_plan(inp)
            if inp.video is None:
                raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
            bounds = {"start_ms": plan.start_ms - BASELINE_MS, "end_ms": plan.end_ms}
            if plan.adaptive:
                bounds["require_eof"] = True
            rows = self.reader.extract(inp.video, **bounds)
            result = evaluate_head_turn(rows, plan)
            return ModuleResult(
                module=Module.HEAD_TURN,
                model_version=self.version,
                status=result.status,
                gate=result.gate,
                quality={"provisional": True, "depth_verified": False},
                evidence=[
                    Evidence(
                        type="text",
                        name="head_reason",
                        value=result.reason,
                        label_vi="Chỉ kiểm thứ tự chuyển động, chưa xác minh chiều sâu",
                    ),
                    Evidence(
                        type="timeseries",
                        name="view_times_ms",
                        value=result.view_times_ms,
                        unit="ms",
                    ),
                ],
                latency_ms=(perf_counter() - started) * 1000,
            )
        except Exception as exc:
            return ModuleResult(
                module=Module.HEAD_TURN,
                model_version=self.version,
                status=exc.status if isinstance(exc, LandmarkError) else Status.ERROR,
                error_code=exc.code if isinstance(exc, LandmarkError) else ErrorCode.E_INTERNAL,
                gate=Gate.UNCLEAR,
                latency_ms=(perf_counter() - started) * 1000,
            )
