"""Local developer trial, not a server-issued or signed authentication challenge."""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass, field, replace

import numpy as np

from vericlue_ml.presence.gaze import GazeEvaluation, GazePlan, evaluate_gaze
from vericlue_ml.presence.head_turn import HeadEvaluation, HeadPlan, direction, evaluate_head_turn
from vericlue_ml.presence.landmarks import FaceObservation

TARGETS = (
    (0.5, 0.5),
    (0.2, 0.7),
    (0.8, 0.3),
    (0.3, 0.2),
    (0.7, 0.8),
    (0.2, 0.4),
    (0.6, 0.2),
    (0.8, 0.7),
)


@dataclass
class WebcamTrial:
    started: float
    trial_id: str = field(default_factory=lambda: secrets.token_hex(16))
    order: tuple[str, ...] = field(
        default_factory=lambda: (
            ("left", "right", "center") if secrets.randbelow(2) else ("right", "left", "center")
        )
    )
    observations: list[FaceObservation] = field(default_factory=list)
    frames: list[tuple[float, np.ndarray, FaceObservation]] = field(default_factory=list)
    # Randomize the path while retaining adequate range in both axes.
    path: tuple[tuple[float, float], ...] = field(
        default_factory=lambda: tuple(secrets.SystemRandom().sample(list(TARGETS), len(TARGETS)))
    )
    gaze_start_ms: float = 5000.0

    @property
    def gaze_plan(self) -> GazePlan:
        return GazePlan(tuple(self.gaze_start_ms + t for t in range(0, 7001, 1000)), self.path)

    @property
    def head_plan(self) -> HeadPlan:
        return HeadPlan(self.gaze_start_ms + 7000, self.duration_ms, self.order, 1000.0)

    @property
    def duration_ms(self) -> float:
        return self.gaze_start_ms + 13000

    def __post_init__(self) -> None:
        if (
            isinstance(self.gaze_start_ms, bool)
            or not isinstance(self.gaze_start_ms, (int, float))
            or not math.isfinite(self.gaze_start_ms)
            or not 5000 <= self.gaze_start_ms <= 10000
        ):
            raise ValueError("Invalid local motion schedule")

    def add(self, acquired: float, frame: np.ndarray, observation: FaceObservation) -> None:
        """Use the host acquisition clock; bound RAM, never synthesize missing samples."""
        elapsed = (acquired - self.started) * 1000
        if not math.isfinite(elapsed) or not 0 <= elapsed <= self.duration_ms + 200:
            return
        if self.observations and elapsed <= self.observations[-1].at_ms:
            return
        if len(self.observations) >= 240:
            return
        row = replace(observation, at_ms=elapsed)
        self.observations.append(row)
        if (
            abs(elapsed - 1000) <= 100
            or self.head_plan.start_ms - 500 <= elapsed <= self.duration_ms
        ) and len(self.frames) < 75:
            self.frames.append((elapsed, frame.copy(), row))

    def cue(self, elapsed: float) -> tuple[str, tuple[float, float] | None]:
        """Return human instructions and the intended target in canvas coordinates."""
        if elapsed < self.gaze_start_ms:
            return "Giữ đầu thẳng, nhìn vào camera", None
        if elapsed < self.head_plan.start_ms:
            plan = self.gaze_plan
            return "Giữ đầu yên, chỉ đưa mắt theo chấm sáng", tuple(
                float(np.interp(elapsed, plan.times, np.asarray(plan.points)[:, axis]))
                for axis in (0, 1)
            )
        if elapsed < self.duration_ms:
            role = self.order[min(2, int((elapsed - self.head_plan.start_ms) // 2000))]
            return {
                "left": "Quay sang trái của bạn, giữ nhẹ",
                "right": "Quay sang phải của bạn, giữ nhẹ",
                "center": "Trở về giữa, nhìn camera",
            }[role], None
        return "Đã thu xong chuyển động", None

    def evaluate(self) -> tuple[GazeEvaluation, HeadEvaluation]:
        return evaluate_gaze(self.observations, self.gaze_plan), evaluate_head_turn(
            self.observations, self.head_plan
        )

    def selected_frames(self, times: dict[str, float]) -> dict[str, np.ndarray]:
        """Require actual observed poses on the exact pixels selected for each role."""
        selected = {}
        for role in ("front", "left", "right"):
            at, frame, row = min(
                self.frames, key=lambda value: (abs(value[0] - times[role]), value[0])
            )
            if (
                abs(at - times[role]) > 100
                or row.face_count != 1
                or any(
                    v is None or not math.isfinite(v)
                    for v in (row.yaw_deg, row.pitch_deg, row.roll_deg)
                )
                or max(abs(row.pitch_deg), abs(row.roll_deg)) > 15
                or direction(row) != ("center" if role == "front" else role)
            ):
                raise ValueError("Missing valid view")
            selected[role] = frame.copy()
        return selected
