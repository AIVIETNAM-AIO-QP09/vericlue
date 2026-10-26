"""Private enrolled-template matching; reuse the loaded LVFace and server-selected pixels.

These protocols require their own calib_ltt artifacts. CCCD-match calibration
cannot stand in for live-template matching. No vector enters ModuleResult.
"""

from __future__ import annotations

import hashlib
import math
from itertools import combinations
from pathlib import Path
from time import perf_counter

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.match import MatchThreshold
from vericlue_ml.face.template import FaceTemplate
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION, VideoFaceMatchDetector
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.head_turn import CENTER_MAX_DEG, MAX_PITCH_ROLL_DEG
from vericlue_ml.presence.landmarks import LandmarkError
from vericlue_ml.presence.session_views import session_views
from vericlue_ml.presence.views import select_frontal_frame, video_sha256

REAUTH_MATCH_VERSION = VIDEO_MATCH_VERSION + "+enrolled-reauth-v1"
RECOVERY_MATCH_VERSION = VIDEO_MATCH_VERSION + "+enrolled-recovery-v1"


def match_enrolled(
    matcher: VideoFaceMatchDetector,
    inp: DetectorInput,
    template: FaceTemplate,
    calibration_path: Path | None,
) -> ModuleResult:
    """Internal worker operation, never an HTTP input or a serialized detector field."""
    started = perf_counter()
    recovery = inp.metadata.get("purpose") == "recovery"
    version = RECOVERY_MATCH_VERSION if recovery else REAUTH_MATCH_VERSION
    try:
        if inp.metadata.get("purpose") not in {"reauth", "recovery"}:
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        template = FaceTemplate.model_validate_json(template.model_dump_json())
        if template.model_version != VIDEO_MATCH_VERSION or inp.video is None:
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        target = expected_dynamic(inp).get("frontal_capture_at_ms") if recovery else 500
        if type(target) is not int or not 0 <= target < 1000:
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        checksum = video_sha256(inp.video)
        if checksum == template.source_video_sha256:
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        frontal = select_frontal_frame(inp.video, target)
        row = matcher.reader.observe(frontal.bgr, at_ms=frontal.at_ms)
        if (
            row.face_count != 1
            or any(not math.isfinite(v) for v in (row.yaw_deg, row.pitch_deg, row.roll_deg))
            or abs(row.yaw_deg) > CENTER_MAX_DEG
            or max(abs(row.pitch_deg), abs(row.roll_deg)) > MAX_PITCH_ROLL_DEG
        ):
            raise LandmarkError(ErrorCode.E_LOW_QUALITY, Status.DEGRADED)
        frames = {"front": frontal.bgr}
        if recovery:
            frames, view_hash = session_views(inp, matcher.reader)
            if view_hash != checksum or not np.array_equal(frames["front"], frontal.bgr):
                raise LandmarkError(ErrorCode.E_INTEGRITY)
        vectors = matcher.embed_frames(frames)
        hashes = [v[1] for v in vectors.values()]
        if (
            len(set(hashes)) != len(hashes)
            or template.pixels_sha256 in hashes
            or video_sha256(inp.video) != checksum
        ):
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        cosine = float(np.clip(np.asarray(template.embedding) @ vectors["front"][0], -1, 1))
        view_cosines = [
            float(np.clip(vectors[a][0] @ vectors[b][0], -1, 1))
            for a, b in combinations(sorted(vectors), 2)
        ]
        artifact = None
        if calibration_path is not None:
            artifact = MatchThreshold.model_validate_json(
                calibration_path.read_text(encoding="utf-8")
            )
            if artifact.model_version != version:
                raise LandmarkError(ErrorCode.E_INTEGRITY)
        consistency = matcher._consistency_threshold
        consistent = bool(
            recovery
            and len(view_cosines) == 3
            and consistency is not None
            and min(view_cosines) >= consistency.threshold
        )
        available = artifact is not None and (not recovery or consistency is not None)
        passed = available and cosine >= artifact.threshold and (not recovery or consistent)
        return ModuleResult(
            module=Module.FACE_MATCH,
            model_version=version,
            status=Status.OK if available else Status.DEGRADED,
            gate=(Gate.PASS if passed else Gate.FAIL) if available else Gate.UNCLEAR,
            score=1 - cosine,
            quality={
                "threshold_available": available,
                "threshold_cosine": artifact.threshold if artifact else None,
                "consistency_verified": consistent,
                "depth_verified": False,
                "enrolled_reference": True,
                "frontal_pose_checked": True,
            },
            evidence=[
                Evidence(type="text", name="source_video_sha256", value=checksum),
                Evidence(
                    type="text", name="reference_account_id", value=inp.metadata.get("account_id")
                ),
                Evidence(
                    type="scalar",
                    name="selected_frontal_frame",
                    value={
                        "target_ms": target,
                        "at_ms": frontal.at_ms,
                        "pixels_sha256": hashlib.sha256(frontal.bgr.tobytes()).hexdigest(),
                    },
                ),
            ],
            latency_ms=(perf_counter() - started) * 1000,
        )
    except Exception as exc:
        return ModuleResult(
            module=Module.FACE_MATCH,
            model_version=version,
            status=getattr(exc, "status", Status.ERROR),
            error_code=getattr(exc, "code", ErrorCode.E_INTERNAL),
            gate=Gate.UNCLEAR,
            latency_ms=(perf_counter() - started) * 1000,
        )
