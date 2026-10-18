"""VOICE-05: offline LatentSync stable_syncnet on the forced-aligned prompt.

Architecture/config/preprocessing sources: ByteDance/LatentSync commit
 a229c3948406bc2cf6eaf4873e662e70c6a04746, configs/syncnet/syncnet_16_pixel_attn.yaml,
 configs/audio.yaml, latentsync/utils/audio.py and latentsync/data/syncnet_dataset.py.
Stable checkpoint is NOT the older five-frame MFCC SyncNet evaluator.

MVP difference: reuse PAD's SCRFD bounding boxes instead of upstream landmark-based
face alignment. Confidence and its score conversion are provisional, not validated
attack probabilities. Audio/video must share the same original recording clock.
No network calls, ASR text, time concatenation, or audio trimming are used here.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.signal import lfilter

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Module, ModuleResult
from vericlue_ml.face.pad import (
    DETECTOR_FILE,
    DETECTOR_MODEL_ID,
    SECOND_FACE_AREA_RATIO,
    FaceFinder,
    PadError,
    ScrfdFaceFinder,
    _manifest_entry,
    _models_root,
    _session,
    _verified_weights,
)
from vericlue_ml.voice.asr import DecodeError, load_audio

if TYPE_CHECKING:
    from vericlue_ml.voice.align import Alignment, ForcedAligner

SYNCNET_MODEL_ID = "syncnet"
SYNCNET_FILE = "stable_syncnet.pt"
SYNCNET_FPS = 25
SYNCNET_FRAMES = 16
SYNCNET_IMAGE_SIZE = 256
AUDIO_SAMPLE_RATE = 16000
MEL_BANDS = 80
MEL_FFT_SIZE = 800
MEL_HOP_SAMPLES = 200
MEL_WINDOW_COLUMNS = 52
# STFT is centered; include rounding and the preemphasis filter's previous sample.
MEL_LEFT_CONTEXT_SECONDS = (MEL_FFT_SIZE / 2 + MEL_HOP_SAMPLES + 1) / AUDIO_SAMPLE_RATE
MEL_RIGHT_SUPPORT_SECONDS = (
    (MEL_WINDOW_COLUMNS - 1) * MEL_HOP_SAMPLES + MEL_FFT_SIZE / 2
) / AUDIO_SAMPLE_RATE
MEL_FMIN_HZ = 55.0
MEL_FMAX_HZ = 7600.0
PREEMPHASIS = 0.97
MIN_LEVEL_DB = -100.0
REFERENCE_LEVEL_DB = 20.0
MAX_ABS_MEL = 4.0
MAX_OFFSET_FRAMES = 15  # +/-600 ms at 25 fps, without leaving the aligned span.
MAX_SYNC_WINDOWS = 4  # Bounded CPU work; evenly spaced anchors, not chosen by score.
CPU_THREADS = 4
CPU_AUDIO_BATCH_SIZE = 4
GPU_AUDIO_BATCH_SIZE = 8
MAX_VIDEO_SECONDS = 120.0
MAX_DECODE_FRAMES = 36000
MAX_RESAMPLE_ERROR_SECONDS = 1 / SYNCNET_FPS
# ADR-0012 section 5: temporary named conversion, never an evaluated probability.
PROVISIONAL_FULL_ATTACK_OFFSET_MS = 500.0
PROVISIONAL_CONFIDENCE_MIN = 0.0
PROVISIONAL_CONFIDENCE_MAX = 1.0


class SyncNetError(RuntimeError):
    """An unavailable/invalid synchrony measurement must not pass."""

    def __init__(
        self, message: str, code: ErrorCode = ErrorCode.E_INTERNAL, status: str = "error"
    ) -> None:
        super().__init__(message)
        self.code, self.status = code, status


@dataclass(frozen=True)
class SyncMeasurement:
    offset_ms: float
    confidence: float
    best_confidence: float
    score: float


def measure_sync(
    video_embeddings: np.ndarray, audio_embeddings: dict[int, np.ndarray]
) -> SyncMeasurement:
    """Compare the same anchors at every offset; confidence is at the original clock."""
    video = np.asarray(video_embeddings, dtype=np.float64)
    if video.ndim != 2 or not video.shape[0] or 0 not in audio_embeddings:
        raise ValueError("Missing synchronized embeddings")
    if not np.isfinite(video).all() or np.any(np.linalg.norm(video, axis=1) <= 0):
        raise ValueError("Invalid visual embedding")
    video = video / np.linalg.norm(video, axis=1, keepdims=True)
    similarities = {}
    for offset, embeddings in audio_embeddings.items():
        values = np.asarray(embeddings, dtype=np.float64)
        if values.shape != video.shape or not np.isfinite(values).all():
            raise ValueError("Invalid audio embeddings")
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        if np.any(norms <= 0):
            raise ValueError("Zero audio embedding")
        similarities[offset] = float(np.mean(np.sum(video * values / norms, axis=1)))
    best = max(similarities, key=lambda offset: (similarities[offset], -abs(offset)))
    confidence = float(
        np.clip(similarities[0], PROVISIONAL_CONFIDENCE_MIN, PROVISIONAL_CONFIDENCE_MAX)
    )
    best_confidence = float(np.clip(similarities[best], 0, 1))
    offset_ms = best * 1000 / SYNCNET_FPS
    score = float(
        np.clip(max(1 - confidence, abs(offset_ms) / PROVISIONAL_FULL_ATTACK_OFFSET_MS), 0, 1)
    )
    return SyncMeasurement(offset_ms, confidence, best_confidence, score)


def _mel_spectrogram(audio: np.ndarray) -> np.ndarray:
    """Original NumPy implementation of upstream librosa Slaney amplitude-mel path."""
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise DecodeError("Invalid audio")
    emphasized = lfilter([1, -PREEMPHASIS], [1], audio).astype(np.float32)
    padded = np.pad(emphasized, (MEL_FFT_SIZE // 2, MEL_FFT_SIZE // 2))
    windows = np.lib.stride_tricks.sliding_window_view(padded, MEL_FFT_SIZE)[::MEL_HOP_SAMPLES]
    hann = np.hanning(MEL_FFT_SIZE + 1)[:-1].astype(np.float32)
    amplitude = np.abs(np.fft.rfft(windows * hann, axis=1)).T

    def hz_to_mel(hz):
        return hz / (200 / 3) if hz < 1000 else 15 + np.log(hz / 1000) / (np.log(6.4) / 27)

    mels = np.linspace(hz_to_mel(MEL_FMIN_HZ), hz_to_mel(MEL_FMAX_HZ), MEL_BANDS + 2)
    hz = np.where(mels < 15, (200 / 3) * mels, 1000 * np.exp((mels - 15) * (np.log(6.4) / 27)))
    frequencies = np.fft.rfftfreq(MEL_FFT_SIZE, 1 / AUDIO_SAMPLE_RATE)
    lower = (frequencies[None, :] - hz[:-2, None]) / (hz[1:-1] - hz[:-2])[:, None]
    upper = (hz[2:, None] - frequencies[None, :]) / (hz[2:] - hz[1:-1])[:, None]
    basis = np.maximum(0, np.minimum(lower, upper)) * (2 / (hz[2:] - hz[:-2]))[:, None]
    mel = basis.astype(np.float32) @ amplitude
    decibels = 20 * np.log10(np.maximum(10 ** (MIN_LEVEL_DB / 20), mel)) - REFERENCE_LEVEL_DB
    return np.clip(
        2 * MAX_ABS_MEL * (decibels - MIN_LEVEL_DB) / -MIN_LEVEL_DB - MAX_ABS_MEL,
        -MAX_ABS_MEL,
        MAX_ABS_MEL,
    ).astype(np.float32)


def _window_starts(alignment: Alignment) -> list[int]:
    """25 fps anchors with all offset candidates entirely inside aligned segments."""
    starts = []
    for segment in alignment.aligned_segments:
        first = (
            math.ceil((segment.start_s + MEL_LEFT_CONTEXT_SECONDS) * SYNCNET_FPS)
            + MAX_OFFSET_FRAMES
        )
        last = (
            math.floor((segment.end_s - MEL_RIGHT_SUPPORT_SECONDS) * SYNCNET_FPS)
            - MAX_OFFSET_FRAMES
        )
        starts.extend(range(first, last + 1, SYNCNET_FRAMES))
    if not starts:
        raise SyncNetError("Aligned prompt is too short", ErrorCode.E_LOW_QUALITY, "degraded")
    if len(starts) > MAX_SYNC_WINDOWS:
        starts = [starts[i] for i in np.linspace(0, len(starts) - 1, MAX_SYNC_WINDOWS, dtype=int)]
    return starts


def _audio_offset_embeddings(
    backend: Any, mel: np.ndarray, starts: list[int]
) -> dict[int, np.ndarray]:
    """Validate every candidate first, then encode each unique mel column once."""
    windows, offset_columns = {}, {}
    for offset in range(-MAX_OFFSET_FRAMES, MAX_OFFSET_FRAMES + 1):
        columns = []
        for start in starts:
            column = int((start + offset) * (AUDIO_SAMPLE_RATE / MEL_HOP_SAMPLES) / SYNCNET_FPS)
            values = mel[:, column : column + MEL_WINDOW_COLUMNS]
            if column < 0 or values.shape != (MEL_BANDS, MEL_WINDOW_COLUMNS):
                raise SyncNetError(
                    "Audio ends before aligned window", ErrorCode.E_LOW_QUALITY, "degraded"
                )
            columns.append(column)
            windows.setdefault(column, values)
        offset_columns[offset] = columns
    if not windows:
        raise ValueError("Missing audio windows")
    batch = getattr(backend, "embed_audio_batch", None)
    encoded = np.asarray(
        batch(np.stack(list(windows.values())))
        if callable(batch)
        else np.stack([backend.embed_audio(values) for values in windows.values()]),
        dtype=np.float64,
    )
    if encoded.ndim != 2 or encoded.shape[0] != len(windows) or not encoded.shape[1]:
        raise ValueError("Invalid batched audio embedding shape")
    norms = np.linalg.norm(encoded, axis=1)
    if not np.isfinite(encoded).all() or not np.isfinite(norms).all() or np.any(norms <= 0):
        raise ValueError("Invalid batched audio embeddings")
    indices = {column: index for index, column in enumerate(windows)}
    return {
        offset: encoded[[indices[column] for column in columns]]
        for offset, columns in offset_columns.items()
    }


def _face_crop(image: np.ndarray, finder: FaceFinder) -> np.ndarray:
    import cv2

    faces = sorted(finder.find(image), key=lambda box: box.area, reverse=True)
    if not faces:
        raise SyncNetError("No face", ErrorCode.E_NO_FACE, "not_applicable")
    if len(faces) > 1 and faces[1].area >= SECOND_FACE_AREA_RATIO * faces[0].area:
        raise SyncNetError("Ambiguous speaker", ErrorCode.E_MULTI_FACE, "degraded")
    box = faces[0]
    height, width = image.shape[:2]
    size = max(box.x2 - box.x1, box.y2 - box.y1)
    cx, cy = (box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2
    x1, y1 = max(0, int(cx - size / 2)), max(0, int(cy - size / 2))
    x2, y2 = min(width, math.ceil(cx + size / 2)), min(height, math.ceil(cy + size / 2))
    if x2 <= x1 or y2 <= y1:
        raise SyncNetError("Invalid face crop", ErrorCode.E_LOW_QUALITY, "degraded")
    crop = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
    # Upstream bicubic antialias resize is done in the backend before normalization.
    return crop


def _read_windows(video: Path, starts: list[int], finder: FaceFinder) -> list[list[np.ndarray]]:
    """Resample real presentation timestamps, including browser variable-frame-rate clips."""
    import cv2

    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise SyncNetError("Undecodable video", ErrorCode.E_DECODE)
        targets = sorted(
            {position for start in starts for position in range(start, start + SYNCNET_FRAMES)}
        )
        if not targets or targets[0] < 0 or targets[-1] / SYNCNET_FPS > MAX_VIDEO_SECONDS:
            raise SyncNetError("Invalid video bounds", ErrorCode.E_DECODE)
        selected, cropped = {}, {}
        cursor = 0
        previous = None

        def remember(position: int, candidate: tuple[float, np.ndarray, int]) -> None:
            timestamp, image, index = candidate
            if abs(timestamp - position / SYNCNET_FPS) > MAX_RESAMPLE_ERROR_SECONDS + 1e-6:
                raise SyncNetError(
                    "Video timestamp gap is too large", ErrorCode.E_LOW_QUALITY, "degraded"
                )
            if index not in cropped:
                cropped[index] = _face_crop(image, finder)
            selected[position] = cropped[index]

        for index in range(MAX_DECODE_FRAMES):
            ok, image = capture.read()
            if not ok:
                # A final frame may be nearest to a target immediately before EOF.
                while previous is not None and cursor < len(targets):
                    remember(targets[cursor], previous)
                    cursor += 1
                if cursor < len(targets):
                    raise SyncNetError("Missing aligned video", ErrorCode.E_DECODE)
                break
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if (
                not math.isfinite(timestamp)
                or timestamp < 0
                or (previous is not None and timestamp <= previous[0])
            ):
                raise SyncNetError(
                    "Missing or non-monotonic presentation timestamps",
                    ErrorCode.E_LOW_QUALITY,
                    "degraded",
                )
            if timestamp > MAX_VIDEO_SECONDS:
                raise SyncNetError("Video timestamp exceeds limit", ErrorCode.E_DECODE)
            current = (timestamp, image, index)
            while cursor < len(targets) and targets[cursor] / SYNCNET_FPS <= timestamp:
                target_s = targets[cursor] / SYNCNET_FPS
                candidate = current
                if previous is not None and abs(target_s - previous[0]) <= abs(
                    timestamp - target_s
                ):
                    candidate = previous
                remember(targets[cursor], candidate)
                cursor += 1
            if cursor == len(targets):
                break
            previous = current
        else:
            raise SyncNetError("Too many video frames", ErrorCode.E_DECODE)
        return [
            [selected[position] for position in range(start, start + SYNCNET_FRAMES)]
            for start in starts
        ]
    finally:
        capture.release()


class StableBackend:
    """Local strict loading with bounded audio minibatches and single video windows."""

    def __init__(self) -> None:
        self.model = None
        self.device = "cpu"
        self.root = None

    def preload(self, *, models_dir: Path, device: str = "cpu") -> None:
        if self.model is not None:
            if self.root != models_dir.resolve() or self.device != device:
                raise SyncNetError("Loaded backend needs restart for a different root/device")
            return
        weights, _ = _verified_weights(models_dir, SYNCNET_MODEL_ID, SYNCNET_FILE)
        import torch

        from vericlue_ml.voice._syncnet_model import StableSyncNet

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device != "cpu" and not (
            device == "cuda" or (device.startswith("cuda:") and device[5:].isdigit())
        ):
            raise SyncNetError("Supported devices: cpu, cuda, cuda:N, auto")
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise SyncNetError("CUDA requested but unavailable")
        self.device = device
        torch.set_num_threads(CPU_THREADS)
        checkpoint = torch.load(weights, map_location="cpu", weights_only=True, mmap=True)
        with torch.device("meta"):
            model = StableSyncNet()
        model.load_state_dict(checkpoint["state_dict"], strict=True, assign=True)
        self.model = model.to(self.device).eval()
        self.root = models_dir.resolve()

    def embed_video(self, crops: list[np.ndarray]) -> np.ndarray:
        import torch
        from torch.nn.functional import interpolate, normalize

        tensors = []
        for crop in crops:
            image = torch.from_numpy(np.ascontiguousarray(crop)).permute(2, 0, 1)[None].float()
            image = interpolate(
                image,
                size=(SYNCNET_IMAGE_SIZE, SYNCNET_IMAGE_SIZE),
                mode="bicubic",
                align_corners=False,
                antialias=True,
            )
            tensors.append(image[0].clamp(0, 255) / 127.5 - 1)
        tensor = torch.stack(tensors).reshape(
            1, SYNCNET_FRAMES * 3, SYNCNET_IMAGE_SIZE, SYNCNET_IMAGE_SIZE
        )
        tensor = tensor[:, :, SYNCNET_IMAGE_SIZE // 2 :, :].to(self.device)
        with torch.inference_mode():
            embedding = self.model.visual_encoder(tensor).flatten(1)
            return normalize(embedding, dim=1)[0].cpu().numpy()

    def embed_audio(self, mel: np.ndarray) -> np.ndarray:
        """Encode one mel window through the same bounded batch path."""
        return self.embed_audio_batch(np.asarray(mel)[None])[0]

    def embed_audio_batch(self, mels: np.ndarray) -> np.ndarray:
        """Encode ordered mel candidates in small minibatches to bound activation RAM."""
        values = np.asarray(mels, dtype=np.float32)
        if (
            values.ndim != 3
            or not values.shape[0]
            or values.shape[1:] != (MEL_BANDS, MEL_WINDOW_COLUMNS)
            or not np.isfinite(values).all()
        ):
            raise ValueError("Expected finite nonempty [N, 80, 52] mel windows")
        if self.model is None:
            raise SyncNetError("Audio backend has not been preloaded")
        import torch
        from torch.nn.functional import normalize

        batch_size = (
            GPU_AUDIO_BATCH_SIZE if self.device.startswith("cuda") else CPU_AUDIO_BATCH_SIZE
        )
        outputs = []
        with torch.inference_mode():
            for start in range(0, len(values), batch_size):
                chunk = values[start : start + batch_size]
                tensor = torch.from_numpy(np.ascontiguousarray(chunk))[:, None].to(self.device)
                embedding = self.model.audio_encoder(tensor).flatten(1)
                output = normalize(embedding, dim=1).cpu().numpy()
                if output.ndim != 2 or output.shape[0] != len(chunk) or not output.shape[1]:
                    raise ValueError("Invalid audio encoder output shape")
                norms = np.linalg.norm(output, axis=1)
                if (
                    not np.isfinite(output).all()
                    or not np.isfinite(norms).all()
                    or np.any(norms <= 0)
                ):
                    raise ValueError("Invalid audio encoder output")
                outputs.append(output)
        return np.concatenate(outputs, axis=0)


class SyncNetDetector:
    """Lipsync plus prompt alignment/splice evidence; all unavailable paths fail closed."""

    name = Module.LIPSYNC.value

    def __init__(
        self,
        models_dir: Path | None = None,
        *,
        aligner: ForcedAligner | Any = None,
        finder: FaceFinder | None = None,
        backend: StableBackend | Any = None,
    ) -> None:
        from vericlue_ml.voice.align import ForcedAligner

        self._root = _models_root(models_dir)
        self._aligner = aligner if aligner is not None else ForcedAligner(models_dir)
        self._finder = finder
        self._backend = backend if backend is not None else StableBackend()
        sync = _manifest_entry(SYNCNET_MODEL_ID, SYNCNET_FILE)["revision"][:8]
        ctc = _manifest_entry("ctc-aligner", "model.safetensors")["revision"][:8]
        scrfd = _manifest_entry(DETECTOR_MODEL_ID, DETECTOR_FILE)["revision"][:8]
        self.version = f"stable-syncnet@{sync}+ctc-aligner@{ctc}+scrfd-10g@{scrfd}+voice05-v2"
        self._lock = threading.RLock()
        self._loaded = False
        self._device = "cpu"

    def preload(self, *, models_dir: Path | None = None, device: str = "cpu") -> None:
        """Verify and load local checkpoints once, including the forced aligner/SCRFD."""
        with self._lock:
            root = _models_root(models_dir) if models_dir is not None else self._root
            if device == "auto":
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            if self._loaded:
                if root.resolve() != self._root.resolve() or device != self._device:
                    raise SyncNetError("Loaded detector needs restart for new configuration")
                return
            self._root, self._device = root, device
            self._aligner.preload(models_dir=root, device=device)
            if self._finder is None:
                weights, _ = _verified_weights(root, DETECTOR_MODEL_ID, DETECTOR_FILE)
                self._finder = ScrfdFaceFinder(_session(weights, device))
            self._backend.preload(models_dir=root, device=device)
            self._loaded = True

    def predict(self, inp: DetectorInput) -> ModuleResult:
        """Measure only original-clock windows contained in the aligned prompt."""
        started = time.perf_counter()
        evidence = []
        try:
            if inp.video is None:
                raise SyncNetError("No video", ErrorCode.E_LOW_QUALITY, "not_applicable")
            if inp.audio is None:
                raise SyncNetError("No audio", ErrorCode.E_DECODE)
            prompt = inp.metadata.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise SyncNetError("Missing server prompt")
            with self._lock:
                self.preload(models_dir=self._root, device=self._device)
                alignment = self._aligner.align(inp.audio, prompt)
                events = [
                    dict(kind=e.kind, start_s=e.start_s, end_s=e.end_s)
                    for e in alignment.splice_events
                ]
                evidence = [
                    Evidence(
                        type="scalar",
                        name="splice_flags",
                        value=len(events),
                        label_vi="Số cờ cắt ghép",
                    ),
                    Evidence(
                        type="segments",
                        name="splice_positions",
                        value=events,
                        unit="s",
                        label_vi="Vị trí cần kiểm tra",
                    ),
                    Evidence(
                        type="segments",
                        name="aligned_prompt",
                        value=[
                            dict(text=s.text, start_s=s.start_s, end_s=s.end_s)
                            for s in alignment.syllables
                        ],
                        unit="s",
                        label_vi="Căn chỉnh câu đề bài",
                    ),
                ]
                starts = _window_starts(alignment)
                crops = _read_windows(inp.video, starts, self._finder)
                mel = _mel_spectrogram(load_audio(inp.audio))
                visual = np.stack([self._backend.embed_video(window) for window in crops])
                audio_embeddings = _audio_offset_embeddings(self._backend, mel, starts)
                result = measure_sync(visual, audio_embeddings)
            evidence += [
                Evidence(
                    type="scalar",
                    name="av_offset_ms",
                    value=result.offset_ms,
                    unit="ms",
                    label_vi="Độ lệch hình–tiếng (dương: tiếng trễ)",
                ),
                Evidence(
                    type="scalar",
                    name="sync_confidence",
                    value=result.confidence,
                    label_vi="Độ tin cậy tại mốc ghi gốc",
                ),
                Evidence(
                    type="scalar",
                    name="best_offset_confidence",
                    value=result.best_confidence,
                    label_vi="Độ tin cậy sau dò lệch",
                ),
                Evidence(
                    type="text", name="calibration_note", value="MVP — không dùng cho báo cáo"
                ),
            ]
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status="ok",
                score=result.score,
                prob_attack=None,
                evidence=evidence,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except SyncNetError as exc:
            status, code = exc.status, exc.code
        except PadError as exc:
            status, code = "error", exc.code
        except DecodeError:
            status, code = "error", ErrorCode.E_DECODE
        except Exception:
            status, code = "error", ErrorCode.E_INTERNAL
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status=status,
            error_code=code,
            evidence=evidence,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
