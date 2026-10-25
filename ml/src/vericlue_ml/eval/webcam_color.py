"""Local screen-color experiment; host clocks and draw requests are not attestations."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
from dataclasses import dataclass, field, replace
from pathlib import Path
from time import perf_counter

import numpy as np

from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.presence.chromapulse import VERSION, ColorPlan, evaluate_colors, log_linear
from vericlue_ml.presence.color_regions import ColorObservation, color_observation
from vericlue_ml.presence.landmarks import FaceObservationReader, observation_from_result

MAX_ROWS = 120
MAX_DRAWS = 512
MAX_DRAW_GAP_MS = 200  # Quality guard, not a security or physical-latency threshold.


def local_color_plan() -> tuple[ColorPlan, int]:
    """Read shared v1 pastel/timing limits; never manufacture a server challenge."""
    path = Path(
        os.environ.get(
            "CHROMAPULSE_CONFIG",
            Path(__file__).resolve().parents[4] / "packages/contracts/chromapulse.json",
        )
    )
    raw = path.read_bytes()
    config = json.loads(raw)
    palette = config["palette"]
    labels = [config["baseline_color"], *palette]
    timing = [
        config["baseline_ms"],
        config["transition_ms"],
        config["tail_ms"],
        config["hold_ms"]["min"],
        config["hold_ms"]["max"],
    ]
    if (
        type(config["version"]) is not int
        or config["version"] != 1
        or type(config["steps"]) is not int
        or config["steps"] != 8
        or len(palette) != 4
        or len(set(palette)) != 4
        or any(not isinstance(c, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in labels)
        or any(type(t) is not int or t <= 0 for t in timing)
    ):
        raise ValueError("Unsupported shared color configuration")
    baseline_ms, transition, tail, low, high = timing
    if low > high or baseline_ms + 8 * (high + transition) + tail > 10_000:
        raise ValueError("Unsupported color duration")
    rgbs = [tuple(int(label[i : i + 2], 16) for i in (1, 3, 5)) for label in labels]
    if len(set(rgbs[1:])) != 4:
        raise ValueError("Palette must contain four distinct colors")
    luminance = np.exp(log_linear(np.asarray(rgbs))) @ np.array([0.2126, 0.7152, 0.0722])
    limits = config["limits"]
    if (
        1000 / (low + transition) > min(2.5, limits["max_changes_per_second"])
        or np.ptp(luminance) > min(0.064, limits["max_luminance_spread"])
        or any(rgb[0] / max(sum(rgb), 1) >= min(0.8, limits["max_red_share"]) for rgb in rgbs)
    ):
        raise ValueError("Shared color configuration exceeds display limits")
    rng = secrets.SystemRandom()
    # Include every palette color, with no adjacent repeat; this remains a LOCAL trial.
    colors = rng.sample(rgbs[1:], 4)
    for _ in range(4):
        colors.append(rng.choice([rgb for rgb in rgbs[1:] if rgb != colors[-1]]))
    starts, ends, cursor = [], [], baseline_ms
    for _ in colors:
        starts.append(cursor)
        cursor += transition + rng.randint(low, high)
        ends.append(cursor)
    return ColorPlan(
        tuple(starts),
        tuple(ends),
        tuple(colors),
        rgbs[0],
        transition,
        hashlib.sha256(raw).hexdigest(),
    ), tail


def observe_live(reader: FaceObservationReader, frame: np.ndarray, *, with_color: bool):
    """One landmark inference yields both pose/eyes and optional color stats in RAM."""
    return reader.measure(
        frame,
        at_ms=0.0,
        transform=lambda result, rgb: (
            observation_from_result(result, 0.0, rgb.shape[1], rgb.shape[0]),
            color_observation(result, rgb, 0.0) if with_color else None,
        ),
    )


@dataclass
class WebcamColorTrial:
    started: float
    plan: ColorPlan
    tail_ms: int
    trial_id: str = field(default_factory=lambda: secrets.token_hex(16))
    observations: list[ColorObservation] = field(default_factory=list)
    draws: list[dict] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        return self.plan.ends[-1] + self.tail_ms

    def add(self, acquired: float, row: ColorObservation | None) -> None:
        """Keep bounded numbers only; reject old/duplicate timestamps, never store pixels."""
        elapsed = (acquired - self.started) * 1000
        if (
            row is None
            or not math.isfinite(elapsed)
            or not 0 <= elapsed <= self.duration_ms
            or len(self.observations) >= MAX_ROWS
            or (self.observations and elapsed <= self.observations[-1].at_ms)
        ):
            return
        self.observations.append(replace(row, at_ms=elapsed))

    def color_at(self, elapsed: float) -> tuple[int, int, int]:
        if elapsed < self.plan.ends[-1]:
            return tuple(int(v) for v in self.plan.rgb_at(np.array([elapsed]))[0])
        fraction = min(1.0, (elapsed - self.plan.ends[-1]) / self.plan.transition_ms)
        return tuple(
            int(math.floor(a + (b - a) * fraction + 0.5))
            for a, b in zip(self.plan.colors[-1], self.plan.baseline, strict=True)
        )

    def record_draw(self, elapsed: float, rgb: tuple[int, int, int]) -> None:
        """Record Tk draw REQUEST time, never claim compositor presentation time."""
        if (
            math.isfinite(elapsed)
            and 0 <= elapsed <= self.duration_ms + 300
            and len(self.draws) < MAX_DRAWS
            and (not self.draws or elapsed > self.draws[-1]["at_ms"])
        ):
            self.draws.append({"at_ms": elapsed, "rgb": list(rgb)})

    def evaluate(self) -> ModuleResult:
        started = perf_counter()
        gaps = np.diff([row["at_ms"] for row in self.draws])
        display_complete = bool(
            len(gaps)
            and self.draws[0]["at_ms"] <= 100
            and self.draws[-1]["at_ms"] >= self.plan.ends[-1]
            and gaps.max() <= MAX_DRAW_GAP_MS
        )
        evaluation = evaluate_colors(self.observations, self.plan) if display_complete else None
        return ModuleResult(
            module=Module.CHROMAPULSE,
            model_version=VERSION + "+local-host-clock-v1",
            status=Status.DEGRADED,
            gate=Gate.UNCLEAR,
            error_code=evaluation.error_code if evaluation else ErrorCode.E_LOW_QUALITY,
            quality={
                **(
                    evaluation.metrics
                    if evaluation
                    else {
                        "calibrated": False,
                        "timing_verified": False,
                        "valid_samples": len(self.observations),
                    }
                ),
                "display_schedule_complete": display_complete,
                "max_draw_gap_ms": float(gaps.max()) if len(gaps) else None,
                "challenge_source": "local_lab_not_server_authenticated",
            },
            evidence=[
                Evidence(
                    type="text",
                    name="chromapulse_reason",
                    value=evaluation.reason if evaluation else "display_schedule_interrupted",
                ),
                Evidence(type="text", name="color_config_sha256", value=self.plan.config_sha256),
                Evidence(
                    type="timeseries",
                    name="color_fit_diagnostic",
                    value=evaluation.series if evaluation else [],
                ),
            ],
            latency_ms=(perf_counter() - started) * 1000,
        )
