"""LVFace identity from a server-timed, pose-checked frontal video frame; no still fallback."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from time import perf_counter

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.match import MATCH_VERSION, FaceMatchDetector, MatchError
from vericlue_ml.face.pad import PadError
from vericlue_ml.face.template import FaceTemplate
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.head_turn import CENTER_MAX_DEG, MAX_PITCH_ROLL_DEG
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError
from vericlue_ml.presence.session_views import session_views
from vericlue_ml.presence.views import select_frontal_frame, video_sha256

VIDEO_MATCH_VERSION = MATCH_VERSION + "+video-frontal-v1"


class VideoFaceMatchDetector(FaceMatchDetector):
    """Reuse LVFace/SCRFD; require video pixels at the current server challenge's frontal time."""

    version = VIDEO_MATCH_VERSION

    def __init__(
        self,
        *,
        reader: FaceObservationReader | None = None,
        with_consistency: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.reader = reader if reader is not None else FaceObservationReader()
        self.with_consistency = with_consistency

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        super().preload(models_dir=models_dir, device=device)
        self.reader.preload(models_dir=Path(models_dir) if models_dir is not None else None)

    def enrollment_template(self, inp: DetectorInput, approved: ModuleResult) -> FaceTemplate:
        """Extract only the frontal pixels of a matching, freshly rechecked server result.

        Internal worker call, never a detector response. The caller must retain its
        plaintext lease until this work finishes and enforce its inference deadline.
        This artifact alone does not authorize account enrollment.
        """
        with self._lock:
            if (
                approved.module != Module.FACE_MATCH
                or approved.model_version != self.version
                or approved.status != Status.OK
                or approved.error_code is not None
                or approved.gate != Gate.PASS
            ):
                raise MatchError(ErrorCode.E_INTEGRITY)
            fresh = self.predict(inp)
            if fresh.status != Status.OK or fresh.gate != Gate.PASS or fresh.error_code is not None:
                raise MatchError(ErrorCode.E_INTEGRITY)

            def provenance(result):
                names = ("source_video_sha256", "selected_frontal_frame")
                selected = {e.name: e.value for e in result.evidence if e.name in names}
                if len(selected) != 2 or any(
                    sum(e.name == name for e in result.evidence) != 1 for name in names
                ):
                    raise MatchError(ErrorCode.E_INTEGRITY)
                return selected

            source = provenance(fresh)
            if provenance(approved) != source:
                raise MatchError(ErrorCode.E_INTEGRITY)
            selected = source["selected_frontal_frame"]
            frame = select_frontal_frame(inp.video, selected["target_ms"])
            vector, pixels_hash = self._embedding(frame.bgr)
            if (
                pixels_hash != selected["pixels_sha256"]
                or video_sha256(inp.video) != source["source_video_sha256"]
            ):
                raise MatchError(ErrorCode.E_INTEGRITY)
            return FaceTemplate(
                session_id=inp.session_id,
                challenge_id=inp.metadata["expected_challenge"]["challenge_id"],
                model_version=self.version,
                preprocessing="arcface112-rgb-minus1to1-v1",
                source_video_sha256=source["source_video_sha256"],
                pixels_sha256=pixels_hash,
                embedding=tuple(float(v) for v in vector),
            )

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = perf_counter()
        try:
            dynamic = expected_dynamic(inp)
            target = dynamic.get("frontal_capture_at_ms")
            baseline = inp.metadata["expected_challenge"].get("baseline_ms")
            if (
                type(target) is not int
                or type(baseline) is not int
                or not 0 <= target < baseline <= 2000
            ):
                raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
            if inp.video is None or inp.reference_image is None:
                raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
            checksum = video_sha256(inp.video)
            frame = select_frontal_frame(inp.video, target)
            row = self.reader.observe(frame.bgr, at_ms=frame.at_ms)
            if row.face_count != 1:
                raise LandmarkError(
                    ErrorCode.E_NO_FACE if row.face_count == 0 else ErrorCode.E_MULTI_FACE,
                    Status.NOT_APPLICABLE,
                )
            if (
                any(
                    type(v) not in (int, float) or not math.isfinite(v)
                    for v in (row.yaw_deg, row.pitch_deg, row.roll_deg)
                )
                or abs(row.yaw_deg) > CENTER_MAX_DEG
                or max(abs(row.pitch_deg), abs(row.roll_deg)) > MAX_PITCH_ROLL_DEG
            ):
                raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
            if video_sha256(inp.video) != checksum:
                raise LandmarkError(ErrorCode.E_INTEGRITY)
            # Ignore client stills/roles; only this server-selected pixel array reaches LVFace.
            frames = {"front": frame.bgr}
            if self.with_consistency:
                frames, view_checksum = session_views(inp, self.reader)
                if view_checksum != checksum or not (frames["front"] == frame.bgr).all():
                    raise LandmarkError(ErrorCode.E_INTEGRITY)
            result = self.predict_frames(inp, frames)
            if video_sha256(inp.video) != checksum:
                raise LandmarkError(ErrorCode.E_INTEGRITY)
            result.quality.update(
                views_from_video=True, frontal_pose_checked=True, depth_verified=False
            )
            result.evidence.extend(
                [
                    Evidence(type="text", name="source_video_sha256", value=checksum),
                    Evidence(
                        type="scalar",
                        name="selected_frontal_frame",
                        value={
                            "target_ms": target,
                            "at_ms": frame.at_ms,
                            "pixels_sha256": hashlib.sha256(frame.bgr.tobytes()).hexdigest(),
                            "yaw_deg": row.yaw_deg,
                            "pitch_deg": row.pitch_deg,
                            "roll_deg": row.roll_deg,
                        },
                    ),
                ]
            )
            result.latency_ms = (perf_counter() - started) * 1000
            return result
        except Exception as exc:
            return ModuleResult(
                module=Module.FACE_MATCH,
                model_version=self.version,
                status=exc.status if isinstance(exc, (LandmarkError, MatchError)) else Status.ERROR,
                error_code=exc.code
                if isinstance(exc, (LandmarkError, PadError))
                else ErrorCode.E_INTERNAL,
                gate=Gate.UNCLEAR,
                latency_ms=(perf_counter() - started) * 1000,
            )
