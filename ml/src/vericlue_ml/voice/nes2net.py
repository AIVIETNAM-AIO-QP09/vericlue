"""NES2Net-X + XLS-R-300M port, isolated CPU diagnostic (VOICE-09).

Upstream Liu-Tianchi/Nes2Net_ASVspoof_ITW@c9fe1177f44040f002cb40def928332d2e261f1e:
easy_inference_demo.py (raw mono 16 kHz, repeat/crop FIRST 64000 samples);
data_utils_SSL.py genSpoof_list (0=spoof, 1=bonafide). Head attribution in
_nes2net_arch.py. Full trained checkpoint already includes the XLS-R backbone.
Transformers graph replaces Fairseq; full frontend parity remains unverified.
Always degraded/unclear, raw spoof-minus-bonafide logit, NEVER prob_attack.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import yaml

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, ModuleResult
from vericlue_ml.voice.antispoof import ModelLoadError, convert_state_dict, verify_file
from vericlue_ml.voice.asr import DecodeError, SpeechNotFound, load_audio, speech_bounds

REVISION = "c9fe1177f44040f002cb40def928332d2e261f1e"
VERSION = f"nes2net-x@{REVISION}+hf4576-cpu-fp32-first4s-v1"
SAMPLE_RATE = 16000
WINDOW_SAMPLES = 64000
MAX_SECONDS = 30
MAX_BYTES = 32 * 1024 * 1024


def prepare_samples(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Require bounded native 16 kHz PCM; do not silently resample/normalize/trim."""
    if (
        type(sample_rate) is not int
        or sample_rate != SAMPLE_RATE
        or not isinstance(samples, np.ndarray)
        or samples.ndim != 1
        or samples.dtype != np.float32
        or not 0 < len(samples) <= MAX_SECONDS * SAMPLE_RATE
        or not np.isfinite(samples).all()
        or np.any(np.abs(samples) > 1)
    ):
        raise DecodeError("Expected bounded mono float32 PCM at 16 kHz")
    if len(samples) < SAMPLE_RATE:
        raise SpeechNotFound("Less than one second")
    window = np.tile(samples, (WINDOW_SAMPLES + len(samples) - 1) // len(samples))[:WINDOW_SAMPLES]
    # VAD is a quality gate ONLY on the scored window, never a transform of model input.
    start, end = speech_bounds(window)
    if end - start < SAMPLE_RATE:
        raise SpeechNotFound("Insufficient speech in scored window")
    return np.array(window, dtype=np.float32, copy=True)


def map_checkpoint(
    state: dict, backbone_shapes: dict, head_shapes: dict
) -> tuple[dict, dict, dict]:
    """Strict coverage of both trained components; reuse audited Fairseq key mapping."""
    frontend, head = {}, {}
    for key, value in state.items():
        if not isinstance(key, str):
            raise ModelLoadError("Invalid checkpoint key")
        if key.startswith("ssl_model.model."):
            frontend["m_ssl.model." + key.removeprefix("ssl_model.model.")] = value
        elif key.startswith("Nested_Res2Net_TDNN."):
            head[key.removeprefix("Nested_Res2Net_TDNN.")] = value
        else:
            raise ModelLoadError("Unknown checkpoint component")
    targets = {"backbone." + key: shape for key, shape in backbone_shapes.items()}
    mapped, report = convert_state_dict(frontend, targets)
    backbone = {key.removeprefix("backbone."): value for key, value in mapped.items()}
    if set(head) != set(head_shapes):
        raise ModelLoadError("Incomplete or unexpected head keys")
    for key, value in head.items():
        if tuple(value.shape) != tuple(head_shapes[key]):
            raise ModelLoadError("Head shape mismatch")
    return backbone, head, {**report, "head_keys": len(head)}


class Nes2NetBackend:
    """Hash first, weights_only CPU load, strict mapping, one cached locked model."""

    def __init__(self, models_dir: Path | None = None) -> None:
        repo = Path(__file__).resolve().parents[4]
        self._repo = repo
        source = Path(os.getenv("NES2NET_CONFIG", repo / "ml/configs/nes2net.yaml"))
        self.config = yaml.safe_load(source.read_text(encoding="utf-8"))
        if (
            self.config["revision"] != REVISION
            or type(self.config["cpu_threads"]) is not int
            or not 1 <= self.config["cpu_threads"] <= 16
        ):
            raise ModelLoadError("Unsupported NES2Net config")
        root = Path(models_dir or os.getenv("MODELS_DIR", repo / "models")).expanduser()
        self.models_dir = (root if root.is_absolute() else repo / root).resolve()
        self._model = None
        self._failed = False
        self._lock = threading.RLock()
        self.model_hashes: dict[str, str] = {}
        self.load_report: dict = {}

    def _checkpoint(self) -> Path:
        path = (self.models_dir / self.config["model_subdir"] / self.config["checkpoint"]).resolve()
        if not path.is_relative_to(self.models_dir):
            raise ModelLoadError("Checkpoint outside model root")
        verify_file(path, self.config["sha256"])
        self.model_hashes = {self.config["checkpoint"]: self.config["sha256"]}
        return path

    def _load_native(self, path: Path):
        import importlib.metadata

        if importlib.metadata.version("transformers") != "4.57.6":
            raise ModelLoadError("Use the pinned NES2Net/face CPU runtime, not the Qwen runtime")
        import torch
        from transformers import Wav2Vec2Config, Wav2Vec2Model

        from vericlue_ml.voice._nes2net_arch import Nested_Res2Net_TDNN

        torch.set_num_threads(self.config["cpu_threads"])

        class Network(torch.nn.Module):
            def __init__(self, config):
                super().__init__()
                self.backbone = Wav2Vec2Model(config)
                self.head = Nested_Res2Net_TDNN(
                    Nes_ratio=(8, 8),
                    input_channel=1024,
                    n_output_logits=2,
                    dilation=2,
                    pool_func="mean",
                    SE_ratio=(1,),
                )

            def forward(self, waveform):
                features = self.backbone(waveform, return_dict=True).last_hidden_state
                return self.head(features.transpose(1, 2))

        config = Wav2Vec2Config(**self.config["backbone"])
        config._attn_implementation = "eager"
        model = Network(config)
        state = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        if (
            not isinstance(state, dict)
            or not state
            or not all(isinstance(value, torch.Tensor) for value in state.values())
        ):
            raise ModelLoadError("Expected tensor-only state dictionary")
        backbone, head, report = map_checkpoint(
            state,
            {k: tuple(v.shape) for k, v in model.backbone.state_dict().items()},
            {k: tuple(v.shape) for k, v in model.head.state_dict().items()},
        )
        model.backbone.load_state_dict(backbone, strict=True)
        model.head.load_state_dict(head, strict=True)
        self.load_report = report
        return model.to(device="cpu", dtype=torch.float32).eval()

    def preload(self, *, models_dir: Path | None = None, device: str | None = None) -> None:
        """Keep loaded root fixed; any load failure is unavailable until restart."""
        with self._lock:
            if device not in (None, "cpu"):
                raise ModelLoadError("NES2Net diagnostic is CPU-only")
            if self._failed:
                raise ModelLoadError("NES2Net unavailable until restart")
            selected = self.models_dir
            if models_dir is not None:
                selected = Path(models_dir).expanduser()
                selected = (selected if selected.is_absolute() else self._repo / selected).resolve()
            if self._model is not None:
                if selected != self.models_dir:
                    raise ModelLoadError("Construct a new backend to change loaded model roots")
                return
            try:
                self.models_dir = selected
                path = self._checkpoint()
                model = self._load_native(path)
                self._checkpoint()
                self._model = model
            except Exception as exc:
                self._failed = True
                self._model = None
                raise ModelLoadError("Cannot load verified local NES2Net") from exc

    def logits(self, window: np.ndarray) -> np.ndarray:
        """Exactly one four-second window; no prompt, VAD transformation or normalization."""
        if (
            window.shape != (WINDOW_SAMPLES,)
            or window.dtype != np.float32
            or not np.isfinite(window).all()
        ):
            raise DecodeError("Invalid NES2Net window")
        import torch

        with self._lock, torch.inference_mode():
            self.preload()
            value = torch.from_numpy(window).unsqueeze(0)
            return self._model(value)[0].float().cpu().numpy()


class Nes2NetDetector:
    """Standalone raw diagnostic; port parity and Vietnamese calibration are pending."""

    name = "voice_spoof"
    version = VERSION

    def __init__(self, models_dir: Path | None = None, *, backend: Any = None) -> None:
        self.backend = backend if backend is not None else Nes2NetBackend(models_dir)

    def preload(self, *, models_dir: Path | None = None, device: str | None = None) -> None:
        self.backend.preload(models_dir=models_dir, device=device)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        """Bound local 16 kHz input; never turn a diagnostic score into acceptance."""
        return self._predict(lambda: self._read_file(inp.audio))

    @staticmethod
    def _read_file(path: Path | None) -> np.ndarray:
        import soundfile as sf

        if path is None or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise DecodeError("Missing or oversized local audio")
        # Reject implicit resampling/channel folding to preserve the native input recipe.
        try:
            info = sf.info(path)
        except (OSError, RuntimeError, ValueError) as exc:
            raise DecodeError("Cannot decode audio header") from exc
        if (
            info.samplerate != SAMPLE_RATE
            or info.channels != 1
            or info.frames > MAX_SECONDS * SAMPLE_RATE
        ):
            raise DecodeError("Use mono 16 kHz audio, up to 30 seconds")
        return load_audio(path, max_seconds=MAX_SECONDS)

    def predict_samples(self, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> ModuleResult:
        """Internal RAM diagnostic; caller supplies mono 16 kHz without hidden conversion."""
        return self._predict(lambda: samples, sample_rate=sample_rate)

    def _predict(self, read, *, sample_rate: int = SAMPLE_RATE) -> ModuleResult:
        started = perf_counter()
        base = dict(module=self.name, model_version=self.version, gate="unclear", prob_attack=None)
        try:
            samples = read()
            window = prepare_samples(samples, sample_rate)
            logits = np.asarray(self.backend.logits(window), dtype=np.float64)
            if logits.shape != (2,) or not np.isfinite(logits).all():
                raise ModelLoadError("Invalid NES2Net logits")
            score = float(logits[0] - logits[1])
            if not np.isfinite(score):
                raise ModelLoadError("Invalid NES2Net margin")
            return ModuleResult(
                **base,
                status="degraded",
                score=score,
                quality={
                    "diagnostic_only": True,
                    "frontend_parity_verified": False,
                    "calibrated": False,
                    "input_seconds": len(samples) / SAMPLE_RATE,
                    "scored_seconds": 4.0,
                    "scored_start_s": 0.0,
                    "truncated": len(samples) > WINDOW_SAMPLES,
                    "repeated_to_four_seconds": len(samples) < WINDOW_SAMPLES,
                },
                evidence=[
                    Evidence(type="scalar", name="logit_spoof", value=float(logits[0])),
                    Evidence(type="scalar", name="logit_bonafide", value=float(logits[1])),
                ],
                latency_ms=(perf_counter() - started) * 1000,
            )
        except SpeechNotFound:
            status, code = "not_applicable", ErrorCode.E_LOW_QUALITY
        except DecodeError:
            status, code = "error", ErrorCode.E_DECODE
        except Exception:
            status, code = "error", ErrorCode.E_INTERNAL
        return ModuleResult(
            **base, status=status, error_code=code, latency_ms=(perf_counter() - started) * 1000
        )
