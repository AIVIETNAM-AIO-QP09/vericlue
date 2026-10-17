# Copyright 2021 The HuggingFace Inc. team.
# Mapping adapted from Transformers v4.39.3 under Apache-2.0.
# Licensed under the Apache License, Version 2.0; see
# third_party/licenses/transformers-Apache-2.0.txt or
# http://www.apache.org/licenses/LICENSE-2.0 .
# Modified for local AntiDeepfake safetensors, strict coverage and modern weight_norm.
# Pooling/head adapted from Copyright 2025, National Institute of Informatics,
# Wanying Ge and Xin Wang; BSD-3-Clause, see
# third_party/licenses/antideepfake-BSD-3-Clause.txt.
# SPDX-License-Identifier: Apache-2.0 AND BSD-3-Clause
"""Offline MMS-300M AntiDeepfake; research/noncommercial checkpoint only.

Sources: AntiDeepfake@0dea622bde8f064c8ee5a557f2598643123fc6b6
models/W2V.py#L69-L98 (temporal average pooling + original Linear head).
HF README@7928e119e09f616b2ce698892e00ca22dbaa40bf#L75-L185:
mono/16k/layer_norm; class 0=fake, 1=real (final inference print).
https://huggingface.co/nii-yamagishilab/mms-300m-anti-deepfake/blob/7928e119e09f616b2ce698892e00ca22dbaa40bf/README.md
Mapping reference: huggingface/transformers v4.39.3
@09f9f566de83eef1f13ee83b5a1bbeebde5c80c1,
src/transformers/models/wav2vec2/convert_wav2vec2_original_pytorch_checkpoint_to_pytorch.py#L42-L65.
CPU parity verified on 4 files/9 windows: max abs logits 2.956390380859375e-05.
See ml/model_cards/antideepfake-mms300m.md; recheck after backend/mapping changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, ModuleResult, Status
from vericlue_ml.voice.asr import DecodeError, SpeechNotFound, trim_silence

logger = logging.getLogger(__name__)
SAMPLE_RATE = 16000
REVISION = "7928e119e09f616b2ce698892e00ca22dbaa40bf"
FAKE_CLASS = 0
IGNORED_PRETRAINING_PREFIXES = (
    "m_ssl.model.quantizer.",
    "m_ssl.model.project_q.",
    "m_ssl.model.final_proj.",
)


class ModelLoadError(RuntimeError):
    """Missing/corrupted/incompatible local checkpoint; never fall back to a random model."""


def verify_file(path: Path, expected_sha256: str) -> None:
    """Verify original bytes before parsing; never fetch or modify model files."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ModelLoadError("Invalid expected SHA-256")
    try:
        with Path(path).open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
    except OSError as exc:
        raise ModelLoadError(f"Missing/unreadable local model file: {path.name}") from exc
    if actual != expected_sha256:
        raise ModelLoadError(
            f"SHA-256 mismatch: {path.name}; expected {expected_sha256}, got {actual}"
        )


def _configuration() -> dict:
    selected = os.getenv("ML_MODELS_CONFIG")
    path = (
        Path(selected) if selected else Path(__file__).resolve().parents[3] / "configs/models.yaml"
    )
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("antispoof", {})


def _root(models_dir: Path | None) -> Path:
    return Path(models_dir or os.getenv("MODELS_DIR") or "models").expanduser().resolve()


def _mapped_key(key: str, targets: dict[str, tuple]) -> str | None:
    if key in ("proj_fc.weight", "proj_fc.bias"):
        return key
    prefix = "m_ssl.model."
    if not key.startswith(prefix):
        return None
    suffix = key[len(prefix) :]
    exact = {"mask_emb": "masked_spec_embed"}
    if suffix in exact:
        return "backbone." + exact[suffix]
    for old, new in (
        ("post_extract_proj.", "feature_projection.projection."),
        ("layer_norm.", "feature_projection.layer_norm."),
        ("encoder.layer_norm.", "encoder.layer_norm."),
    ):
        if suffix.startswith(old):
            return "backbone." + new + suffix[len(old) :]
    conv = re.fullmatch(r"feature_extractor\.conv_layers\.(\d+)\.(0|2|2\.1)\.(weight|bias)", suffix)
    if conv:
        layer, component, param = conv.groups()
        return f"backbone.feature_extractor.conv_layers.{layer}.{'conv' if component == '0' else 'layer_norm'}.{param}"
    if suffix.startswith("encoder.pos_conv.0."):
        param = suffix.removeprefix("encoder.pos_conv.0.")
        modern = {
            "weight_g": "parametrizations.weight.original0",
            "weight_v": "parametrizations.weight.original1",
        }
        candidate = "backbone.encoder.pos_conv_embed.conv." + modern.get(param, param)
        return (
            candidate if candidate in targets else "backbone.encoder.pos_conv_embed.conv." + param
        )
    layer = re.fullmatch(r"encoder\.layers\.(\d+)\.(.+)", suffix)
    if layer:
        index, rest = layer.groups()
        for old, new in (
            ("self_attn.", "attention."),
            ("self_attn_layer_norm.", "layer_norm."),
            ("final_layer_norm.", "final_layer_norm."),
            ("fc1.", "feed_forward.intermediate_dense."),
            ("fc2.", "feed_forward.output_dense."),
        ):
            if rest.startswith(old):
                return f"backbone.encoder.layers.{index}." + new + rest[len(old) :]
    return None


def convert_state_dict(state: dict, target_shapes: dict[str, tuple]) -> tuple[dict, dict]:
    """Map every inference tensor; only explicit pretraining extras can be discarded."""
    mapped, ignored, unexpected = {}, [], []
    for key, value in state.items():
        if key.startswith(IGNORED_PRETRAINING_PREFIXES) or (
            key == "m_ssl.model.mask_emb" and "backbone.masked_spec_embed" not in target_shapes
        ):
            ignored.append(key)
            continue
        target = _mapped_key(key, target_shapes)
        if target is None or target not in target_shapes:
            unexpected.append(key)
            continue
        if target in mapped:
            raise ModelLoadError(f"Duplicate mapping for {target}")
        if tuple(value.shape) != tuple(target_shapes[target]):
            raise ModelLoadError(
                f"Shape mismatch for {key}: {tuple(value.shape)} != {target_shapes[target]}"
            )
        mapped[target] = value
    missing = sorted(set(target_shapes) - set(mapped))
    if missing or unexpected:
        raise ModelLoadError(
            f"Checkpoint coverage failed: missing={missing}, unexpected={sorted(unexpected)}"
        )
    return mapped, {
        "missing_keys": missing,
        "unexpected_keys": unexpected,
        "ignored_keys": sorted(ignored),
        "mapped_keys": len(mapped),
    }


class TorchAntiDeepfakeBackend:
    """Load the verified original Fairseq tensors into an HF inference backbone once."""

    def __init__(self, models_dir: Path | None = None, device: str | None = None) -> None:
        self.config = _configuration()
        self.models_dir = _root(models_dir)
        self.model_dir = self.models_dir / self.config.get("model_subdir", "antideepfake-mms300m")
        self.device = device or os.getenv("DEVICE") or self.config.get("device", "cpu")
        self.model = None
        self.load_report: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._failure: Exception | None = None

    def preload(self) -> None:
        """No network/from_pretrained/remote code; checksum and strict load are mandatory."""
        with self._lock:
            if self._failure is not None:
                raise ModelLoadError(
                    "Backend preload previously failed; restart required"
                ) from self._failure
            if self.model is not None:
                return
            try:
                self._load()
            except Exception as exc:
                self._failure = exc
                raise ModelLoadError(
                    "AntiDeepfake preload failed; verify local model/dependencies"
                ) from exc

    def _load(self) -> None:
        if self.config.get("revision", REVISION) != REVISION:
            raise ModelLoadError("Config revision does not match the pinned model version")
        checksums = self.config.get("sha256", {})
        for filename in ("config.json", "model.safetensors"):
            verify_file(self.model_dir / filename, checksums.get(filename, ""))
        import torch
        from safetensors.torch import load_file
        from transformers import Wav2Vec2Config, Wav2Vec2Model

        if self.device != "cpu" and not re.fullmatch(r"cuda(?::\d+)?", self.device):
            raise ModelLoadError("Supported devices: cpu, cuda or cuda:N")
        if self.device.startswith("cuda") and not torch.cuda.is_available():
            raise ModelLoadError("CUDA requested but unavailable")
        threads = int(self.config.get("cpu_threads", 4))
        if not 1 <= threads <= 64:
            raise ModelLoadError("Invalid cpu_threads")
        torch.set_num_threads(threads)
        config = Wav2Vec2Config.from_dict(
            json.loads((self.model_dir / "config.json").read_text(encoding="utf-8"))
        )
        config.apply_spec_augment = False
        config._attn_implementation = "eager"

        class Network(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.backbone = Wav2Vec2Model(config)
                self.adap_pool1d = torch.nn.AdaptiveAvgPool1d(1)
                self.proj_fc = torch.nn.Linear(config.hidden_size, 2)

            def forward(self, waveform):
                hidden = self.backbone(waveform, return_dict=True).last_hidden_state
                return self.proj_fc(self.adap_pool1d(hidden.transpose(1, 2)).squeeze(-1))

        model = Network()
        state = load_file(str(self.model_dir / "model.safetensors"), device="cpu")
        mapped, self.load_report = convert_state_dict(
            state, {k: tuple(v.shape) for k, v in model.state_dict().items()}
        )
        model.load_state_dict(mapped, strict=True)
        del state, mapped
        self.dtype = torch.float16 if self.device.startswith("cuda") else torch.float32
        self.model = model.to(device=self.device, dtype=self.dtype).eval()

    def logits(self, audio: np.ndarray) -> np.ndarray:
        """Return two raw logits, class order fake/real; input is already layer-normalized."""
        self.preload()
        import torch

        with self._lock, torch.inference_mode():
            waveform = (
                torch.from_numpy(np.asarray(audio, dtype=np.float32))
                .unsqueeze(0)
                .to(device=self.device, dtype=self.dtype)
            )
            return self.model(waveform)[0].float().cpu().numpy()

    __call__ = logits


def load_audio(path: Path) -> np.ndarray:
    """Bounded local decode, mean channels and upstream torchaudio resampling to 16 kHz."""
    try:
        import soundfile as sf

        info = sf.info(path)
        if not 8000 <= info.samplerate <= 192000 or not 1 <= info.channels <= 2:
            raise DecodeError("Unsupported sample rate/channels")
        if info.frames <= 0 or info.frames / info.samplerate > 120:
            raise DecodeError("Empty audio or over 120 seconds")
        audio, rate = sf.read(path, dtype="float32", always_2d=True)
        audio = np.asarray(audio.mean(axis=1), dtype=np.float32)
        if not np.isfinite(audio).all():
            raise DecodeError("Nonfinite audio")
        if rate != SAMPLE_RATE:
            import torch
            from torchaudio.functional import resample

            audio = resample(torch.from_numpy(audio), rate, SAMPLE_RATE).numpy()
        return audio
    except (OSError, RuntimeError, ValueError) as exc:
        raise DecodeError("Cannot decode local audio") from exc


def _prepare_audio(path: Path) -> tuple[np.ndarray, float, float]:
    original = load_audio(path)
    if len(original) < SAMPLE_RATE:
        raise SpeechNotFound("Audio shorter than one second")
    audio = trim_silence(original)
    if len(audio) < SAMPLE_RATE:
        raise SpeechNotFound("Speech after outer-silence trim is shorter than one second")
    offset = (
        (audio.ctypes.data - original.ctypes.data) / original.itemsize / SAMPLE_RATE
        if np.shares_memory(audio, original)
        else 0.0
    )
    return audio, len(original) / SAMPLE_RATE, offset


def preprocess_audio(path: Path) -> tuple[np.ndarray, float]:
    """VAD trims outer silence only, then upstream waveform normalization is per window."""
    audio, duration, _ = _prepare_audio(path)
    return audio, duration


def normalized_window(audio: np.ndarray) -> np.ndarray:
    """Waveform layer_norm without affine, eps=1e-5, as the upstream inference recipe."""
    x = np.asarray(audio, dtype=np.float32)
    return np.asarray(
        (x - x.mean(dtype=np.float64)) / math.sqrt(float(x.var(dtype=np.float64)) + 1e-5),
        dtype=np.float32,
    )


def window_starts(n_samples: int, window: int = 64000, hop: int = 16000) -> list[int]:
    """Full windows with one end-anchored tail; short clips retain their natural length."""
    if n_samples <= 0 or window <= 0 or hop <= 0 or hop > window:
        raise ValueError("Invalid window sizes")
    if n_samples <= window:
        return [0]
    starts = list(range(0, n_samples - window + 1, hop))
    if starts[-1] != n_samples - window:
        starts.append(n_samples - window)
    return starts


def make_windows(audio: np.ndarray) -> list[tuple[float, float, np.ndarray]]:
    """Windows refer to the trimmed input; detector evidence adds the original-file offset."""
    return [
        (
            start / SAMPLE_RATE,
            min(len(audio), start + 64000) / SAMPLE_RATE,
            audio[start : start + 64000],
        )
        for start in window_starts(len(audio))
    ]


class AntiDeepfakeDetector:
    """voice_spoof raw scores only; the router performs required versioned calibration."""

    name = "voice_spoof"

    def __init__(
        self, models_dir: Path | None = None, *, backend: Any = None, device: str | None = None
    ) -> None:
        self.version = (
            f"mms-300m-antideepfake@{REVISION}+voice01-v1-vad1-ln-win4-hop1-tail-meanlogits"
        )
        self._backend = (
            backend if backend is not None else TorchAntiDeepfakeBackend(models_dir, device)
        )
        self._preloaded = False
        self._failure: Exception | None = None
        self._lock = threading.RLock()

    def preload(self) -> None:
        """Load once; failure remains sticky until a new detector/process is constructed."""
        with self._lock:
            if self._failure is not None:
                raise ModelLoadError(
                    "Detector preload previously failed; restart required"
                ) from self._failure
            if not self._preloaded:
                try:
                    prepare = getattr(self._backend, "preload", None)
                    if prepare is not None:
                        prepare()
                    self._preloaded = True
                except Exception as exc:
                    self._failure = exc
                    raise

    def predict(self, inp: DetectorInput) -> ModuleResult:
        """Silence/short → not_applicable, infrastructure failure → error, never raw probability."""
        started = time.perf_counter()
        base = dict(module=self.name, model_version=self.version)
        try:
            if inp.audio is None:
                raise DecodeError("Missing audio")
            audio, original_duration, offset = _prepare_audio(inp.audio)
            with self._lock:
                self.preload()
                windows, logits = [], []
                run = getattr(self._backend, "logits", self._backend)
                for start, end, segment in make_windows(audio):
                    value = np.asarray(run(normalized_window(segment)), dtype=np.float64)
                    if value.shape != (2,) or not np.isfinite(value).all():
                        raise ModelLoadError("Invalid model logits")
                    logits.append(value)
                    probability = _fake_probability(value)
                    windows.append(
                        dict(
                            start_s=start + offset,
                            end_s=end + offset,
                            score=probability,
                            logits=value.tolist(),
                        )
                    )
            score = _fake_probability(np.mean(logits, axis=0))
            return ModuleResult(
                **base,
                status="ok",
                score=score,
                prob_attack=None,
                quality=dict(
                    duration_s=original_duration,
                    speech_duration_s=len(audio) / SAMPLE_RATE,
                    trim_start_s=offset,
                    n_windows=len(windows),
                ),
                evidence=[Evidence(type="timeseries", name="window_scores", value=windows)],
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except SpeechNotFound:
            status, code = Status.NOT_APPLICABLE, ErrorCode.E_LOW_QUALITY
        except DecodeError:
            status, code = Status.ERROR, ErrorCode.E_DECODE
        except Exception:
            logger.exception("AntiDeepfake inference unavailable")
            status, code = Status.ERROR, ErrorCode.E_INTERNAL
        return ModuleResult(
            **base,
            status=status,
            error_code=code,
            prob_attack=None,
            latency_ms=(time.perf_counter() - started) * 1000,
        )


def _fake_probability(logits: np.ndarray) -> float:
    z = logits - np.max(logits)
    probabilities = np.exp(z)
    return float(probabilities[FAKE_CLASS] / probabilities.sum())
