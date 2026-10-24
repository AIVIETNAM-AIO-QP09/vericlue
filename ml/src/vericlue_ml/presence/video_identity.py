"""Offline eye/head motion, identity and optional PAD/deepfake; no authentication decision."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.fsvfm import FsvfmPadDetector
from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.face.match import FaceMatchDetector, MatchError
from vericlue_ml.face.pad import PadError
from vericlue_ml.presence.gaze import GAZE_VERSION, GazeDetector
from vericlue_ml.presence.gaze import parse_plan as parse_gaze_plan
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
    face_deepfake: ModuleResult | None = None
    face_pad: ModuleResult | None = None
    gaze_tracking: ModuleResult | None = None

    def to_contract(self) -> dict[str, Any]:
        results = {
            "head_turn": self.head_turn.to_contract(),
            "face_match": self.face_match.to_contract(),
        }
        if self.face_deepfake is not None:
            results["face_deepfake"] = self.face_deepfake.to_contract()
        if self.face_pad is not None:
            results["face_pad"] = self.face_pad.to_contract()
        if self.gaze_tracking is not None:
            results["gaze_tracking"] = self.gaze_tracking.to_contract()
        return results


def match_video_views(
    inp: DetectorInput,
    *,
    reader: FaceObservationReader,
    matcher: FaceMatchDetector,
    deepfake: FaceDeepfakeDetector | None = None,
    pad: FsvfmPadDetector | None = None,
    with_gaze: bool = False,
    models_dir: Path | None = None,
    device: str | None = None,
) -> VideoIdentityDiagnostic:
    """Select/check frames from the same local video; ignore client image roles and measurements.

    Caller owns the reader lifecycle and server-resolved reference/video paths. This function
    returns independent ModuleResults and never a final citizen pass/retry decision.
    """
    started = perf_counter()
    head = None
    gaze = None
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

    def blocked(detector, module, reason: str) -> ModuleResult | None:
        return (
            unavailable(
                module,
                getattr(detector, "frames_version", detector.version),
                reason=reason,
            )
            if detector is not None
            else None
        )

    def score_frames(detector, module, frames) -> ModuleResult:
        try:
            detector.preload(models_dir=models_dir, device=device)
            return detector.predict_frames(inp, frames)
        except Exception as exc:
            return unavailable(
                module,
                getattr(detector, "frames_version", detector.version),
                status=exc.status if isinstance(exc, (LandmarkError, MatchError)) else Status.ERROR,
                code=exc.code
                if isinstance(exc, (LandmarkError, PadError))
                else ErrorCode.E_INTERNAL,
                reason="model_unavailable",
            )

    def check_source() -> None:
        nonlocal invalidate_head
        try:
            unchanged = video_sha256(inp.video) == original_sha
        except Exception:
            invalidate_head = True
            raise
        if not unchanged:
            invalidate_head = True
            raise LandmarkError(ErrorCode.E_INTEGRITY)

    try:
        plan = parse_head_plan(inp)
        if with_gaze:
            parse_gaze_plan(inp)  # Validate the server binding before native/model preload.
        if inp.video is None or inp.reference_image is None:
            raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
        original_sha = video_sha256(inp.video)
        reader.preload(models_dir=models_dir)
        if with_gaze:
            gaze = GazeDetector(reader).predict(inp)
        head = HeadTurnDetector(reader).predict(inp)
        if with_gaze:
            check_source()
        reason = None
        if head.status != Status.OK or head.gate != Gate.PASS:
            reason = "head_turn_not_passed"
        elif with_gaze and (gaze is None or gaze.status != Status.OK or gaze.gate != Gate.PASS):
            reason = "gaze_tracking_not_passed"
        if reason:
            return VideoIdentityDiagnostic(
                head,
                unavailable(Module.FACE_MATCH, matcher.version, reason=reason),
                blocked(deepfake, Module.FACE_DEEPFAKE, reason),
                blocked(pad, Module.FACE_PAD, reason),
                gaze,
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
        check_source()
        match = score_frames(matcher, Module.FACE_MATCH, frames)
        gend = (
            score_frames(deepfake, Module.FACE_DEEPFAKE, frames) if deepfake is not None else None
        )
        pad_result = score_frames(pad, Module.FACE_PAD, frames) if pad is not None else None
        provenance = [
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
        for measured in (match, gend, pad_result, gaze):
            if measured is not None:
                measured.quality.update(
                    views_from_video=True, depth_verified=False, provisional=True
                )
                measured.evidence.extend(e.model_copy(deep=True) for e in provenance)
        return VideoIdentityDiagnostic(head, match, gend, pad_result, gaze)
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
            unavailable(
                Module.FACE_DEEPFAKE,
                getattr(deepfake, "frames_version", deepfake.version),
                status=status,
                code=code,
                reason="video_identity_unavailable",
            )
            if deepfake is not None
            else None,
            unavailable(
                Module.FACE_PAD,
                getattr(pad, "frames_version", pad.version),
                status=status,
                code=code,
                reason="video_identity_unavailable",
            )
            if pad is not None
            else None,
            (
                unavailable(
                    Module.GAZE_TRACKING,
                    GAZE_VERSION,
                    status=status,
                    code=code,
                    reason="video_identity_unavailable",
                )
                if gaze is None or invalidate_head
                else gaze
            )
            if with_gaze
            else None,
        )
