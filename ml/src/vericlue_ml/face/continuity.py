"""LVFace continuity: server-selected frontal face vs three samples during speech.

Reuse SCRFD/alignment/LVFace preprocessing pinned in face/match.py. Sample at
10/50/90 percent of the actual PCM WAV duration, shifted by signed A/V offset.
This is sampled identity consistency, not PAD, full-video tracking or liveness.
"""

from __future__ import annotations

import hashlib
import io
import math
import wave
from pathlib import Path
from threading import RLock
from time import perf_counter

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.face.enrolled import RECOVERY_MATCH_VERSION
from vericlue_ml.face.match import FaceMatchDetector, MatchThreshold
from vericlue_ml.face.pad import PadError
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.presence.head_turn import CENTER_MAX_DEG, MAX_PITCH_ROLL_DEG
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError
from vericlue_ml.presence.views import (
    SelectedFrame,
    select_frontal_frame,
    select_timed_frames,
    video_sha256,
)

FACE_VOICE_VERSION = VIDEO_MATCH_VERSION + "+face-voice-v1"
VOICE_FRACTIONS = (0.1, 0.5, 0.9)
MAX_WAV_BYTES = 1 << 20


def wav_duration(path: Path) -> tuple[float, str]:
    """Bounded PCM16/mono/16k WAV; use actual data, reject truncated headers."""
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_WAV_BYTES:
        raise LandmarkError(ErrorCode.E_DECODE)
    raw = path.read_bytes()
    if len(raw) > MAX_WAV_BYTES:
        raise LandmarkError(ErrorCode.E_DECODE)
    try:
        with wave.open(io.BytesIO(raw), "rb") as audio:
            frames = audio.getnframes()
            if (
                audio.getnchannels() != 1
                or audio.getsampwidth() != 2
                or audio.getframerate() != 16000
                or audio.getcomptype() != "NONE"
                or not 16000 <= frames <= 160000
                or len(audio.readframes(frames + 1)) != frames * 2
            ):
                raise LandmarkError(ErrorCode.E_DECODE)
    except (wave.Error, EOFError, OSError) as exc:
        raise LandmarkError(ErrorCode.E_DECODE) from exc
    return frames / 16, hashlib.sha256(raw).hexdigest()


def checked_pose(reader: FaceObservationReader, frame: SelectedFrame) -> None:
    row = reader.observe(frame.bgr, at_ms=frame.at_ms)
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


class FaceContinuityDetector:
    name = Module.FACE_CONTINUITY.value
    version = FACE_VOICE_VERSION

    def __init__(
        self,
        matcher: FaceMatchDetector | None = None,
        reader: FaceObservationReader | None = None,
        *,
        calibration_path: Path | None = None,
    ) -> None:
        self.matcher = matcher if matcher is not None else FaceMatchDetector()
        self.reader = reader if reader is not None else FaceObservationReader()
        self.calibration_path = calibration_path
        self._threshold: MatchThreshold | None = None
        self._loaded = self._failed = False
        self._lock = RLock()

    def preload(self, *, models_dir: Path | str | None = None, device: str | None = None) -> None:
        with self._lock:
            if self._failed:
                raise LandmarkError(ErrorCode.E_INTERNAL)
            if self._loaded:
                return
            try:
                self.matcher.preload(models_dir=models_dir, device=device)
                self.reader.preload(models_dir=Path(models_dir) if models_dir is not None else None)
                if self.calibration_path is not None:
                    artifact = MatchThreshold.model_validate_json(
                        self.calibration_path.read_text(encoding="utf-8")
                    )
                    if artifact.model_version != self.version:
                        raise LandmarkError(ErrorCode.E_INTEGRITY)
                    self._threshold = artifact
                self._loaded = True
            except Exception:
                self._failed = True
                raise

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = perf_counter()
        try:
            with self._lock:
                return self._predict(inp, started)
        except Exception as exc:
            return ModuleResult(
                module=Module.FACE_CONTINUITY,
                model_version=self.version,
                status=getattr(exc, "status", Status.ERROR),
                error_code=exc.code
                if isinstance(exc, (LandmarkError, PadError))
                else ErrorCode.E_INTERNAL,
                gate=Gate.UNCLEAR,
                latency_ms=(perf_counter() - started) * 1000,
            )

    def _predict(self, inp: DetectorInput, started: float) -> ModuleResult:
        dynamic = expected_dynamic(inp)
        target = dynamic.get("frontal_capture_at_ms")
        baseline = inp.metadata["expected_challenge"].get("baseline_ms")
        voice_id = inp.metadata.get("voice_challenge_id")
        offset = inp.metadata.get("audio_offset_ms", 0)
        if (
            type(target) is not int
            or type(baseline) is not int
            or not 0 <= target < baseline <= 2000
            or not isinstance(voice_id, str)
            or not 1 <= len(voice_id) <= 80
            or voice_id != inp.metadata.get("expected_voice_challenge_id")
            or type(offset) is not int
            or not -5000 <= offset <= 5000
        ):
            raise LandmarkError(ErrorCode.E_CHALLENGE_MISMATCH)
        if inp.reference_video is None or inp.video is None or inp.audio is None:
            raise LandmarkError(ErrorCode.E_DECODE, Status.DEGRADED)
        approved = ModuleResult.model_validate(inp.metadata.get("face_reference_result"))
        expected_version = (
            RECOVERY_MATCH_VERSION
            if inp.metadata.get("purpose") == "recovery" and inp.metadata.get("account_id")
            else VIDEO_MATCH_VERSION
        )
        if approved.module != Module.FACE_MATCH or approved.model_version != expected_version:
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        reference_hash = video_sha256(inp.reference_video)
        voice_hash = video_sha256(inp.video)
        if voice_hash == reference_hash:
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        duration, audio_hash = wav_duration(inp.audio)
        # Frame sampling always uses decoder PTS, never reported FPS or seek positions.
        targets = dict(
            zip(
                ("early", "middle", "late"),
                (offset + fraction * duration for fraction in VOICE_FRACTIONS),
                strict=True,
            )
        )
        reference = select_frontal_frame(inp.reference_video, target)
        selected = select_timed_frames(inp.video, targets)
        checked_pose(self.reader, reference)
        for frame in selected.values():
            checked_pose(self.reader, frame)
        reference_pixels = hashlib.sha256(reference.bgr.tobytes()).hexdigest()
        hashes = [e.value for e in approved.evidence if e.name == "source_video_sha256"]
        frames = [e.value for e in approved.evidence if e.name == "selected_frontal_frame"]
        if (
            hashes != [reference_hash]
            or len(frames) != 1
            or not isinstance(frames[0], dict)
            or frames[0].get("pixels_sha256") != reference_pixels
            or frames[0].get("target_ms") != target
            or frames[0].get("at_ms") != reference.at_ms
        ):
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        self.preload()
        vectors = self.matcher.embed_frames(
            {
                "reference": reference.bgr,
                **{name: frame.bgr for name, frame in selected.items()},
            }
        )
        similarities = [
            float(np.clip(vectors["reference"][0] @ vectors[name][0], -1, 1)) for name in targets
        ]
        # Detect source changes across decoding/inference; evidence binds both clips and audio.
        if (
            video_sha256(inp.reference_video) != reference_hash
            or video_sha256(inp.video) != voice_hash
            or wav_duration(inp.audio)[1] != audio_hash
            or vectors["reference"][1] != reference_pixels
            or any(
                vectors[name][1] != hashlib.sha256(frame.bgr.tobytes()).hexdigest()
                for name, frame in selected.items()
            )
        ):
            raise LandmarkError(ErrorCode.E_INTEGRITY)
        reference_ok = (
            approved.status == Status.OK
            and approved.gate == Gate.PASS
            and approved.error_code is None
        )
        available = self._threshold is not None
        usable = available and reference_ok
        cosine = min(similarities)
        return ModuleResult(
            module=Module.FACE_CONTINUITY,
            model_version=self.version,
            status=Status.OK if usable else Status.DEGRADED,
            gate=(Gate.PASS if cosine >= self._threshold.threshold else Gate.FAIL)
            if usable
            else Gate.UNCLEAR,
            score=1 - cosine,
            quality={
                "samples": 3,
                "audio_offset_ms": offset,
                "threshold_available": available,
                "threshold_cosine": self._threshold.threshold if available else None,
                "reference_identity_verified": reference_ok,
                "coverage": "three_samples_not_full_video",
            },
            evidence=[
                *[
                    Evidence(type="text", name=name, value=value)
                    for name, value in {
                        "source_video_sha256": reference_hash,
                        "voice_video_sha256": voice_hash,
                        "audio_sha256": audio_hash,
                        "challenge_id": inp.metadata["challenge_id"],
                        "voice_challenge_id": voice_id,
                    }.items()
                ],
                Evidence(type="scalar", name="cosine_similarities", value=similarities),
                Evidence(
                    type="scalar",
                    name="selected_voice_frames",
                    value=[
                        {
                            "fraction": fraction,
                            "target_ms": frame.target_ms,
                            "at_ms": frame.at_ms,
                            "pixels_sha256": vectors[name][1],
                        }
                        for fraction, (name, frame) in zip(
                            VOICE_FRACTIONS, selected.items(), strict=True
                        )
                    ],
                ),
            ],
            latency_ms=(perf_counter() - started) * 1000,
        )
