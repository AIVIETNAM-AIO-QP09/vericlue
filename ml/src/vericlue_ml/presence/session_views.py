"""Server-owned head schedule -> exact pose-checked pixel arrays for session models."""

import math

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Gate, Status
from vericlue_ml.presence.head_turn import (
    MAX_PITCH_ROLL_DEG,
    HeadTurnDetector,
    direction,
    parse_head_plan,
)
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError
from vericlue_ml.presence.views import select_video_frames, video_sha256


def session_views(
    inp: DetectorInput, reader: FaceObservationReader
) -> tuple[dict[str, np.ndarray], str]:
    """Do not accept client poses, selected timestamps, images or frame labels."""
    plan = parse_head_plan(inp)
    if inp.video is None:
        raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
    checksum = video_sha256(inp.video)
    head = HeadTurnDetector(reader).predict(inp)
    if head.status != Status.OK or head.gate != Gate.PASS:
        raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
    evidence = [e.value for e in head.evidence if e.name == "view_times_ms"]
    times = evidence[0] if len(evidence) == 1 else None
    if (
        not isinstance(times, dict)
        or set(times) != {"front", "left", "right"}
        or any(type(t) not in (int, float) or not math.isfinite(t) for t in times.values())
        or times["front"] != plan.frontal_capture_at_ms
        or not plan.start_ms <= times[plan.order[0]] < times[plan.order[1]] <= plan.end_ms
    ):
        raise LandmarkError(ErrorCode.E_INTEGRITY)
    frames = select_video_frames(inp.video, times)
    for role, frame in frames.items():
        row = reader.observe(frame.bgr, at_ms=frame.at_ms)
        if row.face_count != 1:
            raise LandmarkError(
                ErrorCode.E_NO_FACE if row.face_count == 0 else ErrorCode.E_MULTI_FACE
            )
        if (
            any(
                type(v) not in (int, float) or not math.isfinite(v)
                for v in (row.yaw_deg, row.pitch_deg, row.roll_deg)
            )
            or max(abs(row.pitch_deg), abs(row.roll_deg)) > MAX_PITCH_ROLL_DEG
            or direction(row) != ("center" if role == "front" else role)
        ):
            raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
    if video_sha256(inp.video) != checksum:
        raise LandmarkError(ErrorCode.E_INTEGRITY)
    return {role: frame.bgr for role, frame in frames.items()}, checksum
