"""Offline Qwen3-ASR-0.6B HF-native content verification (CPU FP32 diagnostic).

Checkpoint: Qwen/Qwen3-ASR-0.6B-hf at 7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c.
API: transformers v5.13.0, models/qwen3_asr/processing_qwen3_asr.py and
modeling_qwen3_asr.py. Use the installed Apache-2.0 library, no copied model code.
The expected phrase is NEVER passed to the processor/model as context/hotwords.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import re
import threading
from pathlib import Path

import numpy as np
import yaml

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.voice.asr import (
    ASRError,
    DecodeError,
    SpeechNotFound,
    generation_token_budget,
    load_audio,
    trim_silence,
)
from vericlue_ml.voice.challenge import VoiceChallengeDetector

REVISION = "7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c"
VERSION = f"qwen3-asr-06b@{REVISION}+cpu-fp32-content-v1"
MAX_AUDIO_SECONDS = 30
MAX_AUDIO_BYTES = 32 * 1024 * 1024
RUNTIME_FILES = frozenset(
    {
        "chat_template.jinja",
        "config.json",
        "generation_config.json",
        "model.safetensors",
        "processor_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
    }
)


def extract_transcript(raw: str) -> str:
    """Require a Vietnamese ASR envelope; preserve repetitions instead of repairing them."""
    if not isinstance(raw, str) or len(raw) > 8000:
        raise ASRError("Invalid ASR output")
    prefix, separator, text = raw.partition("<asr_text>")
    if not separator or "<asr_text>" in text:
        raise ASRError("Missing or repeated ASR envelope")
    if prefix.strip().casefold() == "language none" and not text.strip():
        raise SpeechNotFound("No speech in ASR output")
    if prefix.strip().casefold() != "language vietnamese" or "<" in text or ">" in text:
        raise ASRError("Unexpected ASR language or control tokens")
    if not text.strip():
        raise SpeechNotFound("Empty ASR transcription")
    return text.strip()


class QwenASR:
    """Bounded local audio, verified files, one model load, serialized generation."""

    version = VERSION

    def __init__(self, models_dir: Path | None = None) -> None:
        repo = Path(__file__).resolve().parents[4]
        config_path = Path(os.getenv("QWEN_ASR_CONFIG", repo / "ml/configs/qwen3_asr.yaml"))
        self.config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if (
            self.config["revision"] != REVISION
            or set(self.config["sha256"]) != RUNTIME_FILES
            or type(self.config["cpu_threads"]) is not int
            or not 1 <= self.config["cpu_threads"] <= 16
        ):
            raise ASRError("Unsupported Qwen ASR configuration")
        self._repo = repo
        self.models_dir = self._root(models_dir or Path(os.getenv("MODELS_DIR", repo / "models")))
        self._model = self._processor = None
        self._lock = threading.RLock()
        self._failed = False
        self.model_hashes: dict[str, str] = {}

    def _root(self, path: Path) -> Path:
        path = Path(path).expanduser()
        return (path if path.is_absolute() else self._repo / path).resolve()

    def _verify(self) -> Path:
        folder = (self.models_dir / self.config["model_subdir"]).resolve()
        if not folder.is_relative_to(self.models_dir):
            raise ASRError("Model folder outside MODELS_DIR")
        hashes = {}
        for name, expected in self.config["sha256"].items():
            path = (folder / name).resolve()
            if not path.is_relative_to(folder) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ASRError("Invalid model file configuration")
            with path.open("rb") as handle:
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
            if actual != expected:
                raise ASRError("Qwen ASR file integrity check failed")
            hashes[name] = actual
        self.model_hashes = hashes
        return folder

    def _load_native(self, folder: Path):
        if importlib.metadata.version("transformers") != "5.13.0":
            raise ASRError("Use the separate pinned Qwen ASR runtime (Transformers 5.13.0)")
        import torch
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        torch.set_num_threads(self.config["cpu_threads"])
        processor = AutoProcessor.from_pretrained(
            str(folder),
            local_files_only=True,
            trust_remote_code=False,
        )
        model = (
            AutoModelForMultimodalLM.from_pretrained(
                str(folder),
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
                dtype=torch.float32,
                attn_implementation="eager",
            )
            .to("cpu")
            .eval()
        )
        return processor, model

    def preload(self, *, models_dir: Path | None = None, device: str | None = None) -> None:
        """Keep the first valid root/model; failures remain unavailable until restart."""
        with self._lock:
            if device not in (None, "cpu"):
                raise ASRError("This diagnostic runtime supports CPU only")
            selected = self._root(models_dir) if models_dir is not None else self.models_dir
            if self._model is not None:
                if selected != self.models_dir:
                    raise ASRError("Cannot switch model roots after loading")
                return
            if self._failed:
                raise ASRError("Qwen ASR unavailable until restart")
            try:
                self.models_dir = selected
                folder = self._verify()
                processor, model = self._load_native(folder)
                self._verify()  # Detect changed files during load as well.
                self._processor, self._model = processor, model
            except Exception as exc:
                self._failed = True
                self._processor = self._model = None
                raise ASRError("Cannot load verified local Qwen ASR") from exc

    def _infer(self, audio: np.ndarray, *, token_budget: int) -> str:
        """Native generation; audio is already local mono 16 kHz, no expected text input."""
        if (
            not isinstance(audio, np.ndarray)
            or audio.ndim != 1
            or not 8000 <= len(audio) <= MAX_AUDIO_SECONDS * 16000
            or not np.isfinite(audio).all()
            or type(token_budget) is not int
            or not 1 <= token_budget <= 256
        ):
            raise ASRError("Invalid bounded ASR input")
        import torch

        with self._lock, torch.inference_mode():
            self.preload()
            inputs = self._processor.apply_transcription_request(
                audio=audio,
                language="Vietnamese",
                sampling_rate=16000,
                return_tensors="pt",
            ).to("cpu", torch.float32)
            prefix_length = inputs["input_ids"].shape[1]
            output = self._model.generate(
                **inputs,
                max_new_tokens=token_budget,
                do_sample=False,
                num_beams=1,
            )
            generated = output[0, prefix_length:]
            eos = self._model.generation_config.eos_token_id
            eos = [eos] if isinstance(eos, int) else eos
            if (
                not len(generated)
                or len(generated) >= token_budget
                or not eos
                or int(generated[-1]) not in eos
            ):
                raise ASRError("ASR decoding incomplete or token budget exhausted")
            # Raw decode deliberately bypasses upstream's repetition-repair postprocessor.
            raw = self._processor.decode(generated, return_format="raw", skip_special_tokens=True)
            return extract_transcript(raw)

    def transcribe(self, path: Path, *, expected_syllable_count: int | None = None) -> str:
        """Only a syllable COUNT affects output bounds; text cannot bias recognition."""
        budget = max(64, generation_token_budget(expected_syllable_count))
        path = Path(path)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_AUDIO_BYTES:
            raise DecodeError("Missing or oversized local audio")
        audio = load_audio(path, max_seconds=MAX_AUDIO_SECONDS)
        audio = trim_silence(audio, mode=1)
        if len(audio) < 8000:
            raise SpeechNotFound("Too little speech")
        return self._infer(audio, token_budget=budget)


class QwenVoiceChallengeDetector(VoiceChallengeDetector):
    """Same existing two-layer matching rules; pass means content matched, not eKYC passed."""

    def __init__(self, asr: QwenASR | None = None) -> None:
        super().__init__(asr if asr is not None else QwenASR())

    def predict(self, inp: DetectorInput) -> ModuleResult:
        result = super().predict(inp)
        return result.model_copy(update={"quality": {**result.quality, "diagnostic_only": True}})
