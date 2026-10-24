"""RAM-only single-container lipsync diagnostic, reusing VOICE-05 Stable SyncNet.

See syncnet.py for pinned source, licenses and preprocessing differences. JPEG
frames are selected on their original relative PTS, never shifted to maximize
confidence. Unknown hardware/driver latency prevents an authentication verdict.
"""

from __future__ import annotations

import math
import threading
from pathlib import Path
from time import perf_counter

import numpy as np

from vericlue_ml.common.av_recording import AVRecording
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, ModuleResult
from vericlue_ml.face.pad import (
    DETECTOR_FILE,
    DETECTOR_MODEL_ID,
    PadError,
    ScrfdFaceFinder,
    _manifest_entry,
    _models_root,
    _verified_weights,
    shared_scrfd_session,
)
from vericlue_ml.voice.align import REVISION as CTC_REVISION
from vericlue_ml.voice.align import AlignmentError, ForcedAligner
from vericlue_ml.voice.asr import SpeechNotFound, speech_bounds
from vericlue_ml.voice.syncnet import (
    MAX_RESAMPLE_ERROR_SECONDS,
    SYNCNET_FILE,
    SYNCNET_FPS,
    SYNCNET_FRAMES,
    SYNCNET_MODEL_ID,
    StableBackend,
    SyncNetError,
    _audio_offset_embeddings,
    _face_crop,
    _mel_spectrogram,
    _window_starts,
    measure_sync,
)

CLOCK = "single_container_pts_audio_origin_v1"


def _version() -> str:
    sync = _manifest_entry(SYNCNET_MODEL_ID, SYNCNET_FILE)["revision"][:8]
    scrfd = _manifest_entry(DETECTOR_MODEL_ID, DETECTOR_FILE)["revision"][:8]
    return f"stable-syncnet@{sync}+ctc@{CTC_REVISION[:8]}+scrfd@{scrfd}+voice12-v1-single-container-mjpeg"


def validate_recording(recording: AVRecording) -> None:
    if not isinstance(recording, AVRecording) or recording.metadata.get("clock") != CLOCK:
        raise SyncNetError("Expected a single-container recording")
    samples = recording.samples
    if (
        recording.sample_rate != 16000
        or samples.dtype != np.float32
        or samples.ndim != 1
        or not 0 < len(samples) <= 21 * 16000
        or not np.isfinite(samples).all()
        or np.any(np.abs(samples) > 1)
        or not 0 < len(recording.frames) <= 1200
    ):
        raise SyncNetError("Invalid bounded A/V recording")
    times = [frame.at_s for frame in recording.frames]
    if (
        not all(math.isfinite(t) and -2 <= t <= 22 for t in times)
        or any(a >= b for a, b in zip(times, times[1:], strict=False))
        or sum(len(f.jpeg) for f in recording.frames) > 64 * 1024 * 1024
    ):
        raise SyncNetError("Invalid original-clock video")


def read_ram_windows(recording: AVRecording, starts: list[int], finder) -> list[list[np.ndarray]]:
    """Decode only selected original JPEGs; same 40 ms timestamp guard as file SyncNet."""
    import cv2

    times = np.array([frame.at_s for frame in recording.frames])
    selected, decoded = {}, {}
    for position in sorted({p for start in starts for p in range(start, start + SYNCNET_FRAMES)}):
        target = position / SYNCNET_FPS
        after = min(int(np.searchsorted(times, target)), len(times) - 1)
        before = max(0, after - 1)
        index = min((before, after), key=lambda i: abs(times[i] - target))
        if abs(times[index] - target) > MAX_RESAMPLE_ERROR_SECONDS + 1e-6:
            raise SyncNetError(
                "Missing aligned video timestamp", ErrorCode.E_LOW_QUALITY, "degraded"
            )
        if index not in decoded:
            image = cv2.imdecode(
                np.frombuffer(recording.frames[index].jpeg, np.uint8), cv2.IMREAD_COLOR
            )
            if image is None or image.ndim != 3 or image.shape[0] > 480 or image.shape[1] > 640:
                raise SyncNetError("Invalid JPEG frame")
            decoded[index] = _face_crop(image, finder)
        selected[position] = decoded[index]
    return [[selected[p] for p in range(start, start + SYNCNET_FRAMES)] for start in starts]


class RamLipSyncDetector:
    """Opt-in lab backend; all results remain unclear and carry no attack probability."""

    name = "lipsync"

    def __init__(
        self, models_dir: Path | None = None, *, aligner=None, finder=None, backend=None
    ) -> None:
        self.version = _version()
        self.root = _models_root(models_dir)
        self.aligner = aligner if aligner is not None else ForcedAligner(models_dir)
        self.finder = finder
        self.backend = backend if backend is not None else StableBackend()
        self._lock = threading.RLock()
        self.loaded = self.failed = False
        self.model_hashes = {}

    def preload(self) -> None:
        with self._lock:
            if self.failed:
                raise RuntimeError("Lipsync unavailable until restart")
            if self.loaded:
                return
            try:
                self.aligner.preload(device="cpu")
                files = [(SYNCNET_MODEL_ID, SYNCNET_FILE)]
                if self.finder is None:
                    files.append((DETECTOR_MODEL_ID, DETECTOR_FILE))
                    session, _ = shared_scrfd_session(self.root, "cpu")
                    self.finder = ScrfdFaceFinder(session)
                self.backend.preload(models_dir=self.root, device="cpu")
                for model, file in files:
                    _verified_weights(self.root, model, file)
                    self.model_hashes[f"{model}/{file}"] = _manifest_entry(model, file)["sha256"]
                self.loaded = True
            except Exception:
                self.failed = True
                self.model_hashes = {}
                raise

    def provenance(self) -> dict:
        return {
            "model_version": self.version,
            "model_loaded": self.loaded,
            "verified_model_hashes": dict(self.model_hashes),
            "ctc_verified_model_hashes": dict(
                getattr(getattr(self.aligner, "_backend", None), "model_hashes", {})
            ),
            "calibrated": False,
            "hardware_sync_verified": False,
        }

    def predict(self, inp: DetectorInput) -> ModuleResult:
        return self.predict_recording(
            inp.metadata.get("av_recording"), prompt=inp.metadata.get("prompt")
        )

    def predict_recording(self, recording: AVRecording, *, prompt: str) -> ModuleResult:
        started = perf_counter()
        base = dict(module=self.name, model_version=self.version, gate="unclear")
        try:
            ForcedAligner.validate_prompt(prompt)
            validate_recording(recording)
            speech_bounds(recording.samples)
            with self._lock:
                self.preload()
                alignment = self.aligner.align_samples(recording.samples, 16000, prompt)
                starts = _window_starts(alignment)
                crops = read_ram_windows(recording, starts, self.finder)
                mel = _mel_spectrogram(recording.samples)
                visual = np.stack([self.backend.embed_video(window) for window in crops])
                audio = _audio_offset_embeddings(self.backend, mel, starts)
                result = measure_sync(visual, audio)
            return ModuleResult(
                **base,
                status="degraded",
                latency_ms=(perf_counter() - started) * 1000,
                quality={
                    "diagnostic_only": True,
                    "hardware_sync_verified": False,
                    "windows": len(starts),
                },
                evidence=[
                    Evidence(type="scalar", name="av_offset_ms", value=result.offset_ms, unit="ms"),
                    Evidence(type="scalar", name="sync_confidence", value=result.confidence),
                    Evidence(
                        type="scalar", name="best_offset_confidence", value=result.best_confidence
                    ),
                    Evidence(
                        type="segments",
                        name="aligned_prompt",
                        value=[
                            {"text": s.text, "start_s": s.start_s, "end_s": s.end_s}
                            for s in alignment.syllables
                        ],
                    ),
                ],
            )
        except SpeechNotFound:
            status, code = "not_applicable", "E_LOW_QUALITY"
        except SyncNetError as exc:
            status, code = exc.status, exc.code
        except AlignmentError:
            status, code = "degraded", "E_LOW_QUALITY"
        except PadError as exc:
            status, code = "error", exc.code
        except Exception:
            status, code = "error", "E_INTERNAL"
        return ModuleResult(
            **base, status=status, error_code=code, latency_ms=(perf_counter() - started) * 1000
        )
