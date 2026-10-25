"""One local color/eye/head schedule; same host clock and trial id, no verdict."""

from __future__ import annotations

import secrets
from contextlib import suppress
from dataclasses import asdict, dataclass

import numpy as np

from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.webcam_color import WebcamColorTrial, local_color_plan
from vericlue_ml.eval.webcam_trial import WebcamTrial
from vericlue_ml.presence.chromapulse import VERSION as COLOR_VERSION
from vericlue_ml.presence.color_regions import ColorObservation
from vericlue_ml.presence.gaze import evaluate_gaze
from vericlue_ml.presence.head_turn import evaluate_head_turn
from vericlue_ml.presence.landmarks import FaceObservation


@dataclass
class PresenceTrial:
    motion: WebcamTrial
    color: WebcamColorTrial

    @classmethod
    def create(cls, started: float) -> PresenceTrial:
        """Preserve the shared palette/pace; place eye/head stages after its tail."""
        plan, tail = local_color_plan()
        trial_id = secrets.token_hex(16)
        color = WebcamColorTrial(started, plan, tail, trial_id=trial_id)
        motion = WebcamTrial(started, gaze_start_ms=color.duration_ms, trial_id=trial_id)
        return cls(motion, color)

    @property
    def started(self) -> float:
        return self.motion.started

    @property
    def duration_ms(self) -> float:
        return self.motion.duration_ms

    def add(
        self,
        acquired: float,
        frame: np.ndarray,
        face: FaceObservation,
        color: ColorObservation | None,
    ) -> None:
        """One acquired frame supplies both readers; their own bounds reject gaps/old data."""
        self.motion.add(acquired, frame, face)
        self.color.add(acquired, color)

    def cue(self, elapsed: float) -> tuple[int, str, tuple | None, tuple | None]:
        """Return step/text/dot/background; caller records actual draw requests separately."""
        text, dot = self.motion.cue(elapsed)
        if elapsed < self.color.duration_ms:
            rgb = self.color.color_at(elapsed)
            return 1, "Giữ đầu yên, nhìn camera · màn hình đổi màu nhẹ", None, rgb
        return (2 if elapsed < self.motion.head_plan.start_ms else 3), text, dot, None

    def evaluate(self) -> tuple[dict, dict[str, np.ndarray]]:
        """Return independent measurements; color failure must not erase motion results."""
        from vericlue_ml.common.result import Gate, Status

        motion = {}
        for name, operation, plan in (
            ("gaze_tracking", evaluate_gaze, self.motion.gaze_plan),
            ("head_turn", evaluate_head_turn, self.motion.head_plan),
        ):
            try:
                motion[name] = asdict(operation(self.motion.observations, plan))
            except Exception:
                motion[name] = {
                    "status": "error",
                    "gate": "unclear",
                    "reason": "evaluation_error",
                    "metrics": {},
                    "error_code": "E_INTERNAL",
                }
        try:
            color = self.color.evaluate()
        except Exception:
            color = ModuleResult(
                module="chromapulse",
                model_version=COLOR_VERSION + "+local-host-clock-v1",
                status="error",
                gate="unclear",
                error_code="E_INTERNAL",
                latency_ms=0,
            )
        frames = {}
        if all(
            value["status"] == Status.OK and value["gate"] == Gate.PASS for value in motion.values()
        ):
            with suppress(ValueError):
                frames = self.motion.selected_frames(motion["head_turn"]["view_times_ms"])
        return {
            "motion": motion,
            "motion_plan": {
                "trial_id": self.motion.trial_id,
                "gaze_plan": asdict(self.motion.gaze_plan),
                "head_plan": asdict(self.motion.head_plan),
                "recipe": "local_color_then_gaze7s_then_head6s_v1",
                "duration_ms": self.duration_ms,
                "authentication_decision": "not_provided",
                "three_views_available": bool(frames),
            },
            "color": color.to_contract(),
            "color_plan": {
                "trial_id": self.color.trial_id,
                "color_plan": asdict(self.color.plan),
                "tail_ms": self.color.tail_ms,
                "draw_requests": list(self.color.draws),
                "timestamp_source": "host_acquisition_and_tk_draw_request_not_attested",
            },
        }, frames

    def wipe(self) -> None:
        """Clear owned pixel copies and numeric trace; not secure erasure of all copies."""
        for _, frame, _ in self.motion.frames:
            frame.fill(0)
        self.motion.frames.clear()
        self.motion.observations.clear()
        self.color.observations.clear()
        self.color.draws.clear()
