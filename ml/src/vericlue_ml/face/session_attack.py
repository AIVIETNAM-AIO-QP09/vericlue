"""FS-VFM/GenD on verified head-view pixels; new sampling never borrows legacy calibrators."""

from pathlib import Path
from time import perf_counter

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, ModuleResult, Status
from vericlue_ml.face.pad import PadError
from vericlue_ml.presence.landmarks import FaceObservationReader, LandmarkError
from vericlue_ml.presence.session_views import session_views
from vericlue_ml.presence.views import video_sha256


class SessionAttackDetector:
    """One cached backend, same server video; raw results are not authentication gates."""

    def __init__(self, backend, reader: FaceObservationReader) -> None:
        self.backend, self.reader = backend, reader
        self.name = backend.name
        self.version = backend.frames_version + "+session-video-v1"

    def preload(self, *, models_dir: Path | None = None, device: str | None = None) -> None:
        self.reader.preload(models_dir=models_dir)
        self.backend.preload(models_dir=models_dir, device=device)
        self.version = self.backend.frames_version + "+session-video-v1"

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = perf_counter()
        try:
            frames, checksum = session_views(inp, self.reader)
            result = self.backend.predict_frames(inp, frames)
            if video_sha256(inp.video) != checksum:
                raise LandmarkError(ErrorCode.E_INTEGRITY)
            result = result.model_copy(
                update={
                    "model_version": self.version,
                    "status": Status.DEGRADED if result.status == Status.OK else result.status,
                    "gate": Gate.UNCLEAR,
                    "prob_attack": None,
                    "latency_ms": (perf_counter() - started) * 1000,
                }
            )
            result.quality.update(session_video=True, calibrated=False, depth_verified=False)
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
