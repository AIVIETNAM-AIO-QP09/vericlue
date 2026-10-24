"""Offline composition of existing head_turn/face_match modules; no authentication decision."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.match import FaceMatchDetector, MatchError
from vericlue_ml.face.pad import PadError
from vericlue_ml.presence.head_turn import (
    HEAD_VERSION,
    MAX_PITCH_ROLL_DEG,
    HeadTurnDetector,
    direction,
    parse_head_plan,
)
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError
from vericlue_ml.presence.views import VIEW_SAMPLER_VERSION, select_video_frames, video_sha256


@dataclass(frozen=True)
class VideoIdentityDiagnostic:
    head_turn: ModuleResult
    face_match: ModuleResult

    def to_contract(self) -> dict[str, Any]:
        return {
            "head_turn": self.head_turn.to_contract(),
            "face_match": self.face_match.to_contract(),
        }


def match_video_views(
    inp: DetectorInput,
    *,
    reader: FaceObservationReader,
    matcher: FaceMatchDetector,
    models_dir: Path | None = None,
    device: str | None = None,
) -> VideoIdentityDiagnostic:
    """Select/check frames from the same local video; ignore client image roles and measurements.

    Caller owns the reader lifecycle and server-resolved reference/video paths. This function
    returns two independent ModuleResults and never a final citizen pass/retry decision.
    """
    started = perf_counter()
    head = None
    invalidate_head = False

    def unavailable(module, version, *, status=Status.DEGRADED, code=None, reason):
        return ModuleResult(
            module=module,
            model_version=version,
            status=status,
            error_code=code,
            gate=Gate.UNCLEAR,
            quality={"provisional": True, "depth_verified": False},
            evidence=[Evidence(type="text", name="video_identity_reason", value=reason)],
            latency_ms=(perf_counter() - started) * 1000,
        )

    try:
        plan = parse_head_plan(inp)
        if inp.video is None or inp.reference_image is None:
            raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
        original_sha = video_sha256(inp.video)
        reader.preload(models_dir=models_dir)
        head = HeadTurnDetector(reader).predict(inp)
        if head.status != Status.OK or head.gate != Gate.PASS:
            return VideoIdentityDiagnostic(
                head, unavailable(Module.FACE_MATCH, matcher.version, reason="head_turn_not_passed")
            )
        entries = [e.value for e in head.evidence if e.name == "view_times_ms"]
        times = entries[0] if len(entries) == 1 else None
        if (
            not isinstance(times, dict)
            or set(times) != {"front", "left", "right"}
            or any(
                isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t)
                for t in times.values()
            )
            or times["front"] != plan.frontal_capture_at_ms
            or not plan.start_ms <= times[plan.order[0]] < times[plan.order[1]] <= plan.end_ms
        ):
            invalidate_head = True
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        selected = select_video_frames(inp.video, times)
        frames = {}
        for role in ("front", "left", "right"):
            frame = selected[role]
            row = reader.observe(frame.bgr, at_ms=frame.at_ms)
            if row.face_count != 1:
                raise LandmarkError(
                    ErrorCode.E_NO_FACE if row.face_count == 0 else ErrorCode.E_MULTI_FACE,
                    Status.NOT_APPLICABLE,
                )
            if (
                any(
                    value is None or not math.isfinite(value)
                    for value in (row.yaw_deg, row.pitch_deg, row.roll_deg)
                )
                or abs(row.pitch_deg) > MAX_PITCH_ROLL_DEG
                or abs(row.roll_deg) > MAX_PITCH_ROLL_DEG
                or direction(row) != ("center" if role == "front" else role)
            ):
                raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
            frames[role] = frame.bgr
        # Storage must still supply the same bytes after both decoder passes.
        if video_sha256(inp.video) != original_sha:
            invalidate_head = True
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        matcher.preload(models_dir=models_dir, device=device)
        match = matcher.predict_frames(inp, frames)
        match.quality.update(views_from_video=True, depth_verified=False, provisional=True)
        match.evidence.extend(
            [
                Evidence(type="text", name="view_sampler", value=VIEW_SAMPLER_VERSION),
                Evidence(type="text", name="source_video_sha256", value=original_sha),
                Evidence(
                    type="timeseries",
                    name="selected_frames",
                    value={
                        role: {
                            "target_ms": frame.target_ms,
                            "at_ms": frame.at_ms,
                            "pixels_sha256": hashlib.sha256(frame.bgr.tobytes()).hexdigest(),
                        }
                        for role, frame in selected.items()
                    },
                    unit="ms",
                ),
            ]
        )
        return VideoIdentityDiagnostic(head, match)
    except Exception as exc:
        status = exc.status if isinstance(exc, (LandmarkError, MatchError)) else Status.ERROR
        code = exc.code if isinstance(exc, (LandmarkError, PadError)) else ErrorCode.E_INTERNAL
        if head is None or invalidate_head:
            head = unavailable(
                Module.HEAD_TURN,
                HEAD_VERSION,
                status=Status.ERROR if code == ErrorCode.E_INTEGRITY else status,
                code=code,
                reason="video_identity_unavailable",
            )
        return VideoIdentityDiagnostic(
            head,
            unavailable(
                Module.FACE_MATCH,
                matcher.version,
                status=status,
                code=code,
                reason="video_identity_unavailable",
            ),
        )
