"""PhoWhisper CPU offline; load model and processor once.

Source: VinAIResearch/PhoWhisper, HF vinai/PhoWhisper-small
revision a86b604c346caf7148c37512eafe783a16420adb (model card/processor).
Whisper generate API: huggingface/transformers v4.57.1,
src/transformers/models/whisper/generation_whisper.py. VAD: py-webrtcvad-wheels.
The ASR interface never accepts the expected challenge text.
"""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path

import numpy as np
import yaml
from scipy.signal import resample_poly


class ASRError(RuntimeError):
    """Unavailable model or inference; never an accepted result."""


class DecodeError(ASRError):
    """Undecodable audio or unsupported limits."""


class SpeechNotFound(ASRError):
    """No speech found."""


def load_audio(path: Path, *, max_seconds: float = 120) -> np.ndarray:
    """Decode bounded local audio as mono float32 at 16 kHz."""
    try:
        import soundfile as sf

        info = sf.info(path)
        if not 8000 <= info.samplerate <= 192000 or not 1 <= info.channels <= 2:
            raise DecodeError("Tần số/kênh audio không hỗ trợ.")
        if info.frames <= 0 or info.frames / info.samplerate > max_seconds:
            raise DecodeError("Audio rỗng hoặc dài quá 120 giây.")
        audio, rate = sf.read(path, dtype="float32", always_2d=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise DecodeError("Không đọc được audio local.") from exc
    if not np.isfinite(audio).all():
        raise DecodeError("Audio có số không hữu hạn.")
    audio = audio.mean(axis=1)
    if rate != 16000:
        divisor = math.gcd(rate, 16000)
        audio = resample_poly(audio, 16000 // divisor, rate // divisor)
    return np.asarray(audio, dtype=np.float32)


def speech_bounds(audio: np.ndarray, *, mode: int = 1) -> tuple[int, int]:
    """WebRTC PCM16 20 ms; return padded outer speech bounds, preserving internal gaps."""
    import webrtcvad

    vad = webrtcvad.Vad(mode)
    frame = 320
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    spoken = []
    for offset in range(0, len(pcm), frame):
        block = pcm[offset : offset + frame]
        if len(block) < frame:
            block = np.pad(block, (0, frame - len(block)))
        if vad.is_speech(block.tobytes(), 16000):
            spoken.append(offset)
    if not spoken:
        raise SpeechNotFound("Không tìm thấy tiếng nói.")
    padding = 3200
    return max(0, spoken[0] - padding), min(len(audio), spoken[-1] + frame + padding)


def trim_silence(audio: np.ndarray, *, mode: int = 1) -> np.ndarray:
    """Trim using explicit speech indices; preserve the original view-based API."""
    start, end = speech_bounds(audio, mode=mode)
    return audio[start:end]


class PhoWhisperASR:
    """Offline transcription without a prompt or hotword."""

    def __init__(self, models_dir: Path | None = None) -> None:
        repo = Path(__file__).resolve().parents[4]
        config_path = Path(os.environ.get("ML_MODELS_CONFIG") or repo / "ml/configs/models.yaml")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")).get("voice", {})
        root = Path(models_dir or os.environ.get("MODELS_DIR", repo / "models"))
        if not root.is_absolute():
            root = repo / root
        self._model_subdir = config.get("model_subdir", "phowhisper")
        self.model_dir = root / self._model_subdir
        revision = config.get("revision", "a86b604c346caf7148c37512eafe783a16420adb")
        self.version = f"phowhisper-small@{revision}+voice04-v1"
        self.vad_mode = config.get("vad_mode", 1)
        self.cpu_threads = int(config.get("cpu_threads", 4))
        if not 1 <= self.cpu_threads <= 64:
            raise ValueError("cpu_threads must be between 1 and 64.")
        self._model = self._processor = None
        self._lock = threading.Lock()

    def _load(self) -> None:
        if self._model is not None:
            return
        if not (self.model_dir / "pytorch_model.bin").is_file():
            raise ASRError(
                "Thiếu PhoWhisper local; chạy download_models.py --only phowhisper trước."
            )
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        torch.set_num_threads(self.cpu_threads)
        try:
            self._processor = WhisperProcessor.from_pretrained(
                str(self.model_dir), local_files_only=True, trust_remote_code=False
            )
            self._model = (
                WhisperForConditionalGeneration.from_pretrained(
                    str(self.model_dir),
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=False,
                    weights_only=True,
                    dtype=torch.float32,
                )
                .to("cpu")
                .eval()
            )
        except (OSError, ValueError, RuntimeError) as exc:
            raise ASRError("Không nạp được PhoWhisper local.") from exc

    def preload(self, *, models_dir: Path | None = None) -> None:
        """Load local weights once before the API accepts inference requests."""
        with self._lock:
            if models_dir is not None:
                target = models_dir.resolve() / self._model_subdir
                if self._model is not None and target != self.model_dir:
                    raise ASRError("ASR đã nạp với MODELS_DIR khác; cần restart.")
                self.model_dir = target
            self._load()

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe local audio only; no expected-text argument."""
        audio = trim_silence(load_audio(audio_path), mode=self.vad_mode)
        with self._lock:
            self._load()
            import torch

            try:
                inputs = self._processor(
                    audio,
                    sampling_rate=16000,
                    return_tensors="pt",
                    return_attention_mask=True,
                    truncation=False,
                )
                with torch.inference_mode():
                    output = self._model.generate(
                        **inputs,
                        language="vi",
                        task="transcribe",
                        condition_on_prev_tokens=False,
                        return_timestamps=True,
                    )
                return self._processor.batch_decode(output, skip_special_tokens=True)[0].strip()
            except (OSError, ValueError, RuntimeError) as exc:
                raise ASRError("Nhận dạng audio thất bại.") from exc
