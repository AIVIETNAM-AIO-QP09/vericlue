"""PRES-02: diagnostic screen-color correspondence, never a calibrated liveness gate.

Implements this repo's ADR-0007 log/background fit and CAP-03 transition timing.
Decoder time vs a planned screen schedule measures apparent video-relative lag;
it does NOT measure sensor-to-display latency or prove a physical skin surface.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.color_regions import (
    REGION_LANDMARKS,
    ColorObservation,
    ColorObservationReader,
)
from vericlue_ml.presence.landmarks import SAMPLE_INTERVAL_MS, LandmarkError

VERSION = "chromapulse-diagnostic@0.1+face-landmarker-f16-1"
MAX_LAG_MS = 300
LAG_STEP_MS = 5  # Search grid, NOT measurement precision (decoder samples are ~100 ms apart).
MIN_SAMPLES = 30
MIN_COVERAGE = 0.8
MAX_GAP_MS = 300
MAX_VIDEO_BYTES = 64 * 1024 * 1024
# Numerical/coverage safeguards only; none of these are calibrated attack thresholds.
MIN_VARIANCE = 1e-10


def _integer(value: Any) -> bool:
    return type(value) is int


@dataclass(frozen=True)
class ColorPlan:
    starts: tuple[int, ...]
    ends: tuple[int, ...]
    colors: tuple[tuple[int, int, int], ...]
    baseline: tuple[int, int, int]
    transition_ms: int
    config_sha256: str

    def rgb_at(self, times: np.ndarray) -> np.ndarray:
        """CAP-03: transition first, then hold; interpolate and round in sRGB."""
        values = np.tile(self.baseline, (len(times), 1)).astype(float)
        for index, (start, end, color) in enumerate(
            zip(self.starts, self.ends, self.colors, strict=True)
        ):
            selected = (times >= start) & (times < end)
            previous = self.colors[index - 1] if index else self.baseline
            fraction = np.minimum(1, (times[selected] - start) / self.transition_ms)
            values[selected] = np.asarray(previous) + fraction[:, None] * (
                np.asarray(color) - previous
            )
        return np.floor(values + 0.5)


def parse_plan(inp: DetectorInput) -> ColorPlan:
    """Use a server-owned dynamic challenge bound to this session and attempt."""
    dynamic = expected_dynamic(inp)
    challenge = inp.metadata["expected_challenge"]
    config_path = Path(
        os.environ.get(
            "CHROMAPULSE_CONFIG",
            Path(__file__).resolve().parents[4] / "packages/contracts/chromapulse.json",
        )
    )
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    rows = challenge.get("color_sequence")
    cursor = challenge.get("baseline_ms", config["baseline_ms"])
    if (
        not _integer(cursor)
        or cursor != config["baseline_ms"]
        or not isinstance(rows, list)
        or len(rows) != config["steps"]
    ):
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    starts, ends, colors = [], [], []
    previous = None
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("rgb"), str)
            or not re.fullmatch(r"#[0-9a-fA-F]{6}", row["rgb"])
            or not _integer(row.get("hold_ms"))
            or not config["hold_ms"]["min"] <= row["hold_ms"] <= config["hold_ms"]["max"]
            or not _integer(row.get("transition_ms"))
            or row["transition_ms"] != config["transition_ms"]
            or row["rgb"].lower() == previous
        ):
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        previous = row["rgb"].lower()
        starts.append(cursor)
        cursor += row["hold_ms"] + row["transition_ms"]
        ends.append(cursor)
        colors.append(tuple(int(row["rgb"][i : i + 2], 16) for i in (1, 3, 5)))
    gaze = dynamic.get("gaze_points")
    if (
        cursor > 30_000
        or not isinstance(gaze, list)
        or not gaze
        or not isinstance(gaze[0], dict)
        or not _integer(gaze[0].get("at_ms"))
        or gaze[0]["at_ms"] != cursor
    ):
        raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
    base = tuple(int(config["baseline_color"][i : i + 2], 16) for i in (1, 3, 5))
    return ColorPlan(
        tuple(starts),
        tuple(ends),
        tuple(colors),
        base,
        config["transition_ms"],
        hashlib.sha256(config_bytes).hexdigest(),
    )


def log_linear(rgb: np.ndarray) -> np.ndarray:
    """sRGB inverse transfer then log; epsilon is a numerical guard, not a threshold."""
    srgb = np.asarray(rgb, dtype=float) / 255
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    return np.log(np.maximum(linear, 1e-8))


@dataclass(frozen=True)
class ColorEvaluation:
    reason: str
    metrics: dict[str, float | str | bool | None]
    series: list[dict[str, Any]]
    error_code: ErrorCode = ErrorCode.E_LOW_QUALITY


def evaluate_colors(rows: list[ColorObservation], plan: ColorPlan) -> ColorEvaluation:
    """Fit each region on common support across lags; report in-sample fit only."""
    metrics: dict[str, float | str | bool | None] = {
        "calibrated": False,
        "timing_verified": False,
        "client_measurements_used": False,
        "sampling_interval_ms": SAMPLE_INTERVAL_MS,
        "lag_grid_ms": LAG_STEP_MS,
    }

    def unavailable(reason: str, code: ErrorCode = ErrorCode.E_LOW_QUALITY):
        return ColorEvaluation(reason, metrics, [], code)

    if not rows:
        return unavailable("no_observations", ErrorCode.E_NO_FACE)
    ts = np.asarray([row.at_ms for row in rows], dtype=float)
    if not np.isfinite(ts).all() or np.any(np.diff(ts) <= 0):
        return unavailable("invalid_timestamps", ErrorCode.E_DECODE)
    start, end = plan.starts[0] + MAX_LAG_MS, plan.ends[-1]
    window = [row for row in rows if start <= row.at_ms < end]
    if any(row.face_count > 1 for row in window):
        return unavailable("multiple_faces", ErrorCode.E_MULTI_FACE)
    if window and all(row.face_count == 0 for row in window):
        return unavailable("no_face", ErrorCode.E_NO_FACE)
    names = (*REGION_LANDMARKS, "background")

    def usable(row):
        if row.face_count != 1:
            return False
        for name in names:
            stat = row.regions.get(name)
            if stat is None or stat.rgb_trim is None or stat.pixels < 1:
                return False
            value = np.asarray(stat.rgb_trim)
            if (
                value.shape != (3,)
                or not np.isfinite(value).all()
                or np.any(value <= 0)
                or np.any(value > 255)
                or not math.isfinite(stat.excluded_fraction)
                or not 0 <= stat.excluded_fraction < 1
            ):
                return False
        return True

    valid = [row for row in window if usable(row)]
    expected_count = (end - start) / SAMPLE_INTERVAL_MS
    metrics.update(valid_samples=len(valid), coverage=min(1.0, len(valid) / expected_count))
    if len(valid) < MIN_SAMPLES or metrics["coverage"] < MIN_COVERAGE:
        return unavailable("insufficient_color_coverage")
    metrics["max_excluded_fraction"] = max(
        row.regions[name].excluded_fraction for row in valid for name in names
    )
    times = np.asarray([row.at_ms for row in valid])
    if (
        times[0] > start + SAMPLE_INTERVAL_MS * 2
        or times[-1] < end - SAMPLE_INTERVAL_MS * 2
        or np.diff(times).max() > MAX_GAP_MS
    ):
        return unavailable("incomplete_time_window")
    measured = np.asarray([[row.regions[name].rgb_trim for name in names] for row in valid])
    response = log_linear(measured[:, :5]) - log_linear(measured[:, 5:])
    y = response.reshape(len(valid), -1)
    total_ss = float(np.sum((y - y.mean(axis=0)) ** 2))
    metrics["response_amplitude_log"] = float(np.linalg.norm(np.ptp(y, axis=0)))
    if total_ss / y.size < MIN_VARIANCE:
        return unavailable("unobservable_response")
    best = None
    candidates = []
    for lag in range(0, MAX_LAG_MS + 1, LAG_STEP_MS):
        x = log_linear(plan.rgb_at(times - lag))
        centered = x - x.mean(axis=0)
        scale = np.std(x, axis=0)
        if np.any(scale < 1e-9):
            continue
        design = np.column_stack((centered / scale, np.ones(len(x))))
        coefficients, _, rank, singular = np.linalg.lstsq(design, y, rcond=None)
        if rank < 4:
            continue
        predicted = design @ coefficients
        residual_ss = float(np.sum((y - predicted) ** 2))
        r2 = 1 - residual_ss / total_ss
        candidates.append((r2, lag))
        if best is None or r2 > best[0]:
            best = (r2, lag, predicted, float(singular[0] / singular[-1]))
    if best is None:
        return unavailable("insufficient_color_excitation")
    r2, lag, predicted, condition = best
    near = [time for score, time in candidates if score >= r2 - 1e-4]
    metrics.update(
        fit_r2_in_sample=r2,
        apparent_lag_ms=lag,
        near_best_lag_min_ms=min(near),
        near_best_lag_max_ms=max(near),
        lag_at_search_boundary=lag in (0, MAX_LAG_MS),
        design_condition_number=condition,
    )
    for index, name in enumerate(REGION_LANDMARKS):
        truth = response[:, index]
        denom = float(np.sum((truth - truth.mean(axis=0)) ** 2))
        metrics[f"fit_r2_{name}"] = (
            1 - float(np.sum((truth - predicted[:, index * 3 : index * 3 + 3]) ** 2)) / denom
            if denom / truth.size >= MIN_VARIANCE
            else None
        )
    series = [
        {
            "at_ms": float(time),
            "planned_rgb_at_apparent_lag": color.tolist(),
            "mean_log_skin_minus_background": actual.tolist(),
            "fitted_mean": fitted.tolist(),
        }
        for time, color, actual, fitted in zip(
            times,
            plan.rgb_at(times - lag),
            response.mean(axis=1),
            predicted.reshape(-1, 5, 3).mean(axis=1),
            strict=True,
        )
    ]
    return ColorEvaluation("uncalibrated_timing_unverified", metrics, series)


def _video_hash(path: Path) -> str:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_VIDEO_BYTES:
        raise LandmarkError(ErrorCode.E_DECODE)
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class ChromaPulseDetector:
    """Explicit diagnostic only: every outcome is unclear, never an authentication pass."""

    name = Module.CHROMAPULSE.value
    version = VERSION

    def __init__(self, reader: ColorObservationReader | None = None) -> None:
        self.reader = reader if reader is not None else ColorObservationReader()

    def preload(self, **kwargs) -> None:
        self.reader.preload(**kwargs)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = perf_counter()
        try:
            plan = parse_plan(inp)
            if inp.video is None:
                raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
            checksum = _video_hash(inp.video)
            rows = self.reader.extract(inp.video, start_ms=0, end_ms=plan.ends[-1])
            if _video_hash(inp.video) != checksum:
                raise LandmarkError(ErrorCode.E_INTEGRITY)
            evaluation = evaluate_colors(rows, plan)
            return ModuleResult(
                module=Module.CHROMAPULSE,
                model_version=self.version,
                status=Status.DEGRADED,
                gate=Gate.UNCLEAR,
                error_code=evaluation.error_code,
                quality=evaluation.metrics,
                evidence=[
                    Evidence(type="text", name="chromapulse_reason", value=evaluation.reason),
                    Evidence(type="text", name="video_sha256", value=checksum),
                    Evidence(type="text", name="color_config_sha256", value=plan.config_sha256),
                    Evidence(
                        type="timeseries",
                        name="color_fit_diagnostic",
                        value=evaluation.series,
                        label_vi="Khớp màu thử nghiệm — chưa hiệu chỉnh, chưa kiểm đồng hồ",
                    ),
                ],
                latency_ms=(perf_counter() - started) * 1000,
            )
        except Exception as exc:
            return ModuleResult(
                module=Module.CHROMAPULSE,
                model_version=self.version,
                status=exc.status if isinstance(exc, LandmarkError) else Status.ERROR,
                gate=Gate.UNCLEAR,
                error_code=exc.code if isinstance(exc, LandmarkError) else ErrorCode.E_INTERNAL,
                latency_ms=(perf_counter() - started) * 1000,
            )
