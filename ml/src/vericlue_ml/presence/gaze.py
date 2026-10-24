"""LIVE-02: experimental eye-motion correspondence, not an absolute screen-gaze estimator.

MediaPipe iris tracking itself does not locate the viewed point or recognize identity:
https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/iris.md
Rule constants below are provisional, uncalibrated, and not attack-rate measurements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.landmarks import FaceObservation, FaceObservationReader, LandmarkError

GAZE_VERSION = "gaze-rules@0.1+face-landmarker-f16-1"
MIN_VALID_SAMPLES = 45
MIN_COVERAGE = 0.80
MAX_GAP_MS = 300
EDGE_TOLERANCE_MS = 200
MAX_HEAD_DEVIATION_DEG = 12
MAX_HEAD_OFFSET_DEG = 20
MIN_IRIS_SPAN = (0.025, 0.015)
MIN_TARGET_SPAN = 0.20
MIN_CORRELATION = 0.60
MAX_LAG_MS = 350
LAG_STEP_MS = 50


@dataclass(frozen=True)
class GazePlan:
    times: tuple[float, ...]
    points: tuple[tuple[float, float], ...]


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_plan(inp: DetectorInput) -> GazePlan:
    """Accept only the server's expected_challenge, bound to this session and attempt."""
    dynamic = expected_dynamic(inp)
    rows = dynamic.get("gaze_points")
    if not isinstance(rows, list) or len(rows) != 8:
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    times, points = [], []
    for row in rows:
        if not isinstance(row, dict) or not all(_number(row.get(k)) for k in ("x", "y", "at_ms")):
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        x, y, time = row["x"], row["y"], row["at_ms"]
        if not (0.1 <= x <= 0.9 and 0.1 <= y <= 0.9 and 0 <= time <= 30_000):
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        if times and not 0 < time - times[-1] <= 1500:
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        times.append(float(time))
        points.append((float(x), float(y)))
    if times[-1] - times[0] != 7000 or np.ptp(points, axis=0).min() < MIN_TARGET_SPAN:
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    return GazePlan(tuple(times), tuple(points))


@dataclass(frozen=True)
class GazeEvaluation:
    status: Status
    gate: Gate
    reason: str
    metrics: dict[str, float]
    error_code: ErrorCode | None = None


def evaluate_gaze(observations: list[FaceObservation], plan: GazePlan) -> GazeEvaluation:
    """Compare both axes over one fixed time window, with a small positive response lag."""

    def unavailable(reason, metrics=None, code=ErrorCode.E_LOW_QUALITY):
        return GazeEvaluation(Status.DEGRADED, Gate.UNCLEAR, reason, metrics or {}, code)

    if not observations:
        return unavailable("no_observations", code=ErrorCode.E_NO_FACE)
    times = np.asarray([row.at_ms for row in observations], dtype=float)
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        return unavailable("invalid_timestamps", code=ErrorCode.E_DECODE)
    window = [row for row in observations if plan.times[0] <= row.at_ms <= plan.times[-1]]
    if any(row.face_count > 1 for row in window):
        return GazeEvaluation(
            Status.NOT_APPLICABLE, Gate.UNCLEAR, "multiple_faces", {}, ErrorCode.E_MULTI_FACE
        )
    if window and all(row.face_count == 0 for row in window):
        return GazeEvaluation(
            Status.NOT_APPLICABLE, Gate.UNCLEAR, "no_face", {}, ErrorCode.E_NO_FACE
        )
    valid = [
        row
        for row in window
        if row.face_count == 1
        and all(
            _number(getattr(row, key))
            for key in ("gaze_x", "gaze_y", "yaw_deg", "pitch_deg", "roll_deg")
        )
    ]
    expected_count = (plan.times[-1] - plan.times[0]) / 100 + 1
    metrics = {
        "valid_samples": float(len(valid)),
        "coverage": min(len(valid) / expected_count, 1.0),
    }
    if len(valid) < MIN_VALID_SAMPLES or metrics["coverage"] < MIN_COVERAGE:
        return unavailable("insufficient_coverage", metrics)
    ts = np.asarray([row.at_ms for row in valid])
    if (
        ts[0] > plan.times[0] + EDGE_TOLERANCE_MS
        or ts[-1] < plan.times[-1] - EDGE_TOLERANCE_MS
        or np.diff(ts).max() > MAX_GAP_MS
    ):
        return unavailable("incomplete_time_window", metrics)
    poses = np.asarray([(row.yaw_deg, row.pitch_deg, row.roll_deg) for row in valid])
    deviation = float(np.max(np.abs(poses - np.median(poses, axis=0))))
    metrics["head_deviation_deg"] = deviation
    if deviation > MAX_HEAD_DEVIATION_DEG or np.max(np.abs(poses)) > MAX_HEAD_OFFSET_DEG:
        return unavailable("head_not_still", metrics)
    actual = np.asarray([(row.gaze_x, row.gaze_y) for row in valid])
    spans = np.ptp(actual, axis=0)
    metrics.update({"iris_span_x": float(spans[0]), "iris_span_y": float(spans[1])})
    if np.any(spans < MIN_IRIS_SPAN):
        return GazeEvaluation(Status.OK, Gate.FAIL, "eyes_not_following", metrics)
    # Compare every candidate lag on exactly the same support, rather than trim to a lucky suffix.
    common = ts >= plan.times[0] + MAX_LAG_MS
    actual = actual[common]
    target = np.asarray(plan.points)
    best = (-1.0, -1.0, 0)
    for lag in range(0, MAX_LAG_MS + 1, LAG_STEP_MS):
        expected = np.column_stack(
            [np.interp(ts[common] - lag, plan.times, target[:, axis]) for axis in (0, 1)]
        )
        correlations = []
        for axis in (0, 1):
            x, y = actual[:, axis], expected[:, axis]
            if np.std(x) < 1e-9 or np.std(y) < 1e-9:
                correlations.append(-1.0)
            else:
                correlations.append(float(np.corrcoef(x, y)[0, 1]))
        if min(correlations) > min(best[:2]):
            best = (*correlations, lag)
    metrics.update({"correlation_x": best[0], "correlation_y": best[1], "lag_ms": float(best[2])})
    matched = min(best[:2]) >= MIN_CORRELATION
    return GazeEvaluation(
        Status.OK,
        Gate.PASS if matched else Gate.FAIL,
        "matched" if matched else "trajectory_mismatch",
        metrics,
    )


class GazeDetector:
    """Offline CPU landmark extraction plus provisional, fail-closed correspondence rules."""

    name = Module.GAZE_TRACKING.value
    version = GAZE_VERSION

    def __init__(self, reader: FaceObservationReader | None = None) -> None:
        self.reader = reader if reader is not None else FaceObservationReader()

    def preload(self, **kwargs) -> None:
        self.reader.preload(**kwargs)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = perf_counter()
        try:
            plan = parse_plan(inp)
            if inp.video is None:
                raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
            observations = self.reader.extract(
                inp.video, start_ms=plan.times[0], end_ms=plan.times[-1]
            )
            evaluation = evaluate_gaze(observations, plan)
            return ModuleResult(
                module=Module.GAZE_TRACKING,
                model_version=self.version,
                status=evaluation.status,
                gate=evaluation.gate,
                error_code=evaluation.error_code,
                quality={**evaluation.metrics, "provisional": True},
                evidence=[
                    Evidence(
                        type="text",
                        name="gaze_reason",
                        value=evaluation.reason,
                        label_vi="Đối chiếu chuyển động mắt — thử nghiệm, chưa hiệu chỉnh",
                    )
                ],
                latency_ms=(perf_counter() - started) * 1000,
            )
        except Exception as exc:
            return ModuleResult(
                module=Module.GAZE_TRACKING,
                model_version=self.version,
                status=exc.status if isinstance(exc, LandmarkError) else Status.ERROR,
                error_code=exc.code if isinstance(exc, LandmarkError) else ErrorCode.E_INTERNAL,
                gate=Gate.UNCLEAR,
                latency_ms=(perf_counter() - started) * 1000,
            )
