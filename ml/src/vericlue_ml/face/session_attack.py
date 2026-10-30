"""FS-VFM/GenD on verified head-view pixels; new sampling never borrows legacy calibrators."""

import math
from pathlib import Path
from time import perf_counter

from vericlue_ml.common.calibration import CalibrationError, CalibrationStore, Calibrator
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, ModuleResult, Status
from vericlue_ml.face.pad import PadError
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError
from vericlue_ml.presence.session_views import session_views
from vericlue_ml.presence.views import video_sha256


class SessionAttackDetector:
    """Same verified video; only a fitted artifact for this exact protocol supplies probability."""

    def __init__(
        self, backend, reader: FaceObservationReader, calibrators: CalibrationStore | None = None
    ) -> None:
        self.backend, self.reader = backend, reader
        self.name = backend.name
        self.version = backend.frames_version + "+session-video-v1"
        self.calibrators = calibrators if calibrators is not None else CalibrationStore()
        self._checked_version: str | None = None
        self._calibrator: Calibrator | None = None

    def _artifact(self) -> Calibrator | None:
        if self._checked_version != self.version:
            self._checked_version = self.version
            self._calibrator = None
            try:
                artifact = self.calibrators.load(self.name, self.version)
                if isinstance(artifact, Calibrator) and not artifact.provisional:
                    self._calibrator = artifact
            except CalibrationError:
                pass  # Missing/invalid artifacts keep the existing diagnostic-only behavior.
        return self._calibrator

    def preload(self, *, models_dir: Path | None = None, device: str | None = None) -> None:
        self.reader.preload(models_dir=models_dir)
        self.backend.preload(models_dir=models_dir, device=device)
        self.version = self.backend.frames_version + "+session-video-v1"
        self._artifact()

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = perf_counter()
        try:
            frames, checksum = session_views(inp, self.reader)
            result = self.backend.predict_frames(inp, frames)
            if video_sha256(inp.video) != checksum:
                raise LandmarkError(ErrorCode.E_INTEGRITY)
            if result.module != self.name or result.model_version != self.backend.frames_version:
                raise LandmarkError(ErrorCode.E_INTEGRITY)
            status = result.status
            if status == Status.OK and result.error_code is not None:
                status = Status.ERROR
            score = result.score
            if score is None or not math.isfinite(score) or not 0 <= score <= 1:
                score = None
                if status == Status.OK:
                    status = Status.DEGRADED
            artifact = self._artifact() if status == Status.OK else None
            calibrated = artifact is not None
            probability = float(artifact.predict([score])[0]) if calibrated else None
            if status == Status.OK and not calibrated:
                status = Status.DEGRADED
            result = result.model_copy(
                deep=True,
                update={
                    "model_version": self.version,
                    "status": status,
                    "score": score,
                    "gate": Gate.UNCLEAR,
                    "prob_attack": probability,
                    "latency_ms": (perf_counter() - started) * 1000,
                },
            )
            result.quality.update(session_video=True, calibrated=calibrated, depth_verified=False)
            result.evidence.append(
                Evidence(type="text", name="source_video_sha256", value=checksum)
            )
            return result
        except Exception as exc:
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status=exc.status if isinstance(exc, LandmarkError) else Status.ERROR,
                error_code=exc.code
                if isinstance(exc, (LandmarkError, PadError))
                else ErrorCode.E_INTERNAL,
                gate=Gate.UNCLEAR,
                latency_ms=(perf_counter() - started) * 1000,
            )
