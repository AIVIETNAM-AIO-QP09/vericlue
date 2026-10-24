"""Offline CTC alignment of the server prompt, never the ASR transcript (VOICE-05).

Model: MahmoudAshraf/mms-300m-1130-forced-aligner@49402e9577b1158620820667c218cd494cc44486
(CC-BY-NC-4.0 weights). Inference recipe reference: ctc-forced-aligner
@64293cc6d711e57666c4a8b098e9fd93b381fd88, alignment_utils.py and text_utils.py:
https://github.com/MahmoudAshraf97/ctc-forced-aligner/tree/64293cc6d711e57666c4a8b098e9fd93b381fd88
Mono 16 kHz waveform -> CTC log probabilities; blank=0; artificial wildcard=31.
The Viterbi implementation below is original NumPy code, with no upstream code copied.
Vietnamese-only normalization uses existing normalize_text/strip_diacritics instead of
upstream uroman; original syllable text is retained. This is not a multilingual romanizer.
Adjacent wildcard/blank frames dominated by a boundary character extend that character's
span, preventing the neutral wildcard from swallowing sustained initial/final sounds.
All event thresholds are provisional demo rules, not statistical evidence of editing.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from vericlue_ml.voice.asr import DecodeError, load_audio
from vericlue_ml.voice.challenge import normalize_text, strip_diacritics

REVISION = "49402e9577b1158620820667c218cd494cc44486"
SAMPLE_RATE = 16000
CTC_BLANK_ID = 0
CTC_FRAME_SECONDS = 0.02
MAX_AUDIO_SECONDS = 120
MAX_PROMPT_CHARACTERS = 512
MAX_PAUSE_SECONDS = 1.0
MIN_SYLLABLE_SECONDS = 0.06
MAX_SYLLABLE_SECONDS = 1.2
MAX_INTERNAL_STAR_SECONDS = 1.0
EXPECTED_FILES = {
    "config.json": "2af7f73073d212b0ef91d3c73839355ca504c24a6b361c58a9e4e64210376ba9",
    "preprocessor_config.json": "6334d6e0c5f2084c9a99b85ddff243cbc79dbaa4aa790bcddf8c41c496fab6fb",
    "special_tokens_map.json": "5e4d1f5e759d74cb1c2fe1d165cfc62b5237aa904de759380cd6f43042eec723",
    "tokenizer_config.json": "e0fe11ce3a3231f3147b4539a93b30a9aefaca0c2717fbd35881695610417497",
    "vocab.json": "6b6f1632d08b489faf2c954eb70e71f39d0861053feb9ae40da59cfa8d0ef5bb",
    "model.safetensors": "9aa5229a1af4d7714285cfa14bcaab6af2a39a9e810b475722b24975d5cb1dab",
}


class AlignmentError(ValueError):
    """The expected prompt cannot be aligned to usable local audio/emissions."""


class AlignmentLoadError(RuntimeError):
    """The pinned local CTC model is unavailable; never fetch or substitute weights."""


@dataclass(frozen=True)
class TimeSpan:
    start_s: float
    end_s: float


@dataclass(frozen=True)
class SyllableSpan:
    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class SpliceEvent:
    kind: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class Alignment:
    syllables: tuple[SyllableSpan, ...]
    stars: tuple[TimeSpan, ...]
    aligned_segments: tuple[TimeSpan, ...]
    splice_events: tuple[SpliceEvent, ...]

    @property
    def start_s(self) -> float:
        return self.syllables[0].start_s

    @property
    def end_s(self) -> float:
        return self.syllables[-1].end_s


def _verify_model_files(directory: Path) -> dict[str, str]:
    verified = {}
    for name, expected in EXPECTED_FILES.items():
        try:
            with (directory / name).open("rb") as handle:
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
        except OSError as exc:
            raise AlignmentLoadError(f"Missing CTC asset: {name}") from exc
        if actual != expected:
            raise AlignmentLoadError(f"CTC asset SHA-256 mismatch: {name}")
        verified[name] = actual
    return verified


def _root(models_dir: Path | None) -> Path:
    repo = Path(__file__).resolve().parents[4]
    root = Path(models_dir or os.getenv("MODELS_DIR", str(repo / "models"))).expanduser()
    return (root if root.is_absolute() else repo / root).resolve()


class TorchCTCBackend:
    """Load only verified local safetensors, using the upstream direct-waveform recipe."""

    def __init__(self, models_dir: Path | None = None) -> None:
        repo = Path(__file__).resolve().parents[4]
        selected = Path(os.getenv("ML_MODELS_CONFIG", str(repo / "ml/configs/models.yaml")))
        config = yaml.safe_load(selected.read_text(encoding="utf-8")).get("alignment", {})
        if config.get("revision", REVISION) != REVISION:
            raise AlignmentLoadError("CTC configuration revision differs from the pinned model")
        self.model_subdir = config.get("model_subdir", "ctc-aligner")
        self.cpu_threads = int(config.get("cpu_threads", 2))
        if not 1 <= self.cpu_threads <= 64:
            raise AlignmentLoadError("Invalid CTC cpu_threads")
        self.models_dir = _root(models_dir)
        self.model = self.processor = None
        self.model_hashes: dict[str, str] = {}
        self.vocabulary: dict[str, int] = {}
        self._failure: Exception | None = None
        self._lock = threading.RLock()
        self.device = "cpu"

    def preload(self, *, models_dir: Path | None = None, device: str = "cpu") -> None:
        """Verify every asset before constructing a processor or model; load once."""
        with self._lock:
            if self._failure is not None:
                raise AlignmentLoadError(
                    "CTC preload previously failed; restart required"
                ) from self._failure
            requested = _root(models_dir) if models_dir is not None else self.models_dir
            if self.model is not None:
                if requested != self.models_dir or device != self.device:
                    raise AlignmentLoadError("CTC backend already loaded with another root/device")
                return
            try:
                directory = requested / self.model_subdir
                _verify_model_files(directory)
                import torch
                from transformers import AutoModelForCTC, AutoProcessor

                if device != "cpu" and not (
                    device == "cuda" or (device.startswith("cuda:") and device[5:].isdigit())
                ):
                    raise AlignmentLoadError("Supported CTC devices: cpu, cuda, cuda:N")
                if device.startswith("cuda") and not torch.cuda.is_available():
                    raise AlignmentLoadError("CUDA requested but unavailable")
                torch.set_num_threads(self.cpu_threads)
                processor = AutoProcessor.from_pretrained(
                    str(directory), local_files_only=True, trust_remote_code=False
                )
                vocabulary = processor.tokenizer.get_vocab()
                if vocabulary.get("<blank>") != CTC_BLANK_ID or sorted(vocabulary.values()) != list(
                    range(31)
                ):
                    raise AlignmentLoadError("Unexpected pinned CTC vocabulary")
                model, report = AutoModelForCTC.from_pretrained(
                    str(directory),
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                    dtype=torch.float32,
                    attn_implementation="eager",
                    output_loading_info=True,
                )
                if any(
                    report.get(k)
                    for k in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")
                ):
                    raise AlignmentLoadError("CTC checkpoint coverage is incomplete")
                if model.config.inputs_to_logits_ratio != 320 or model.config.vocab_size != 31:
                    raise AlignmentLoadError("Unexpected pinned CTC stride/vocabulary size")
                model = model.to(device).eval()
                verified = _verify_model_files(directory)
                self.processor, self.model = processor, model
                self.model_hashes = verified or {}
                self.vocabulary = vocabulary
                self.models_dir, self.device = requested, device
            except Exception as exc:
                self._failure = exc
                raise AlignmentLoadError("Cannot preload verified local CTC model") from exc

    def emissions(self, audio: np.ndarray) -> tuple[np.ndarray, float]:
        """Return the 31 real-class log probabilities; no feature extractor normalization."""
        with self._lock:
            self.preload(device=self.device)
            import torch

            waveform = (
                torch.from_numpy(np.asarray(audio, dtype=np.float32)).unsqueeze(0).to(self.device)
            )
            with torch.inference_mode():
                logits = self.model(waveform).logits[0]
                values = torch.log_softmax(logits, dim=-1).float().cpu().numpy()
            return values, CTC_FRAME_SECONDS


def _ctc_viterbi(log_probabilities: np.ndarray, targets: list[int]) -> np.ndarray:
    """Original CTC dynamic program; return state indices so repeated tokens stay distinct."""
    frames = log_probabilities.shape[0]
    repeats = sum(a == b for a, b in zip(targets, targets[1:], strict=False))
    if not targets or frames < len(targets) + repeats:
        raise AlignmentError("Not enough CTC frames for the server prompt")
    states = np.full(2 * len(targets) + 1, CTC_BLANK_ID, dtype=np.int64)
    states[1::2] = targets
    count = states.size
    back = np.zeros((frames, count), dtype=np.uint8)
    previous = np.full(count, -np.inf)
    previous[:2] = log_probabilities[0, states[:2]]
    can_skip = np.zeros(count, dtype=bool)
    can_skip[2:] = (states[2:] != CTC_BLANK_ID) & (states[2:] != states[:-2])
    for frame in range(1, frames):
        step = np.concatenate(([-np.inf], previous[:-1]))
        skip = np.concatenate(([-np.inf, -np.inf], previous[:-2]))
        skip[~can_skip] = -np.inf
        candidates = np.stack((previous, step, skip))
        choices = candidates.argmax(axis=0)
        back[frame] = choices
        previous = candidates[choices, np.arange(count)] + log_probabilities[frame, states]
    last = count - 2 + int(previous[-1] > previous[-2])
    if not np.isfinite(previous[last]):
        raise AlignmentError("No finite CTC alignment path")
    path = np.empty(frames, dtype=np.int64)
    for frame in range(frames - 1, -1, -1):
        path[frame] = last
        if frame:
            last -= int(back[frame, last])
    return path


def align_emissions(
    emissions: np.ndarray,
    prompt: str,
    vocabulary: dict[str, int],
    frame_seconds: float = CTC_FRAME_SECONDS,
) -> Alignment:
    """Align original prompt syllables; preserve raw gaps and interior wildcard intervals."""
    values = np.asarray(emissions, dtype=np.float64)
    if (
        values.ndim != 2
        or not values.shape[0]
        or values.shape[1] != len(vocabulary)
        or not np.isfinite(values).all()
        or vocabulary.get("<blank>") != CTC_BLANK_ID
        or sorted(vocabulary.values()) != list(range(len(vocabulary)))
        or not math.isfinite(frame_seconds)
        or frame_seconds <= 0
    ):
        raise AlignmentError("Invalid CTC emissions, vocabulary, or frame stride")
    normalized = normalize_text(prompt)
    if not normalized or len(normalized) > MAX_PROMPT_CHARACTERS:
        raise AlignmentError("Server prompt is empty or too long")
    syllables = normalized.split()
    romanized = [strip_diacritics(text) for text in syllables]
    if any(
        not token or any(c not in vocabulary or not c.isascii() or not c.isalpha() for c in token)
        for token in romanized
    ):
        raise AlignmentError("Prompt contains unsupported Vietnamese alignment characters")
    star = len(vocabulary)
    targets: list[int] = [star]
    boundaries = []
    for word in romanized:
        first = len(targets)
        targets.extend(vocabulary[c] for c in word)
        boundaries.append((first, len(targets) - 1))
        targets.append(star)
    starred = np.column_stack((values, np.zeros(values.shape[0])))
    path = _ctc_viterbi(starred, targets)
    winners = values.argmax(axis=1)
    target_for_state = np.zeros(2 * len(targets) + 1, dtype=np.int64)
    target_for_state[1::2] = targets
    # Restore only contiguous, posterior-supported edge characters. No audio concatenation.
    for first, last in boundaries:
        for token, direction in ((first, -1), (last, 1)):
            state = 2 * token + 1
            positions = np.flatnonzero(path == state)
            if not positions.size:
                raise AlignmentError("Prompt token has no aligned frames")
            cursor = int(positions[0] if direction < 0 else positions[-1]) + direction
            while 0 <= cursor < len(path):
                existing = target_for_state[path[cursor]]
                if existing not in {CTC_BLANK_ID, star} or winners[cursor] != targets[token]:
                    break
                path[cursor] = state
                cursor += direction
    aligned = []
    for text, (first, last) in zip(syllables, boundaries, strict=True):
        frames = np.flatnonzero((path >= 2 * first + 1) & (path <= 2 * last + 1))
        aligned.append(
            SyllableSpan(
                text, int(frames[0]) * frame_seconds, (int(frames[-1]) + 1) * frame_seconds
            )
        )
    star_spans = []
    is_star = target_for_state[path] == star
    edges = np.diff(np.concatenate(([False], is_star, [False])).astype(int))
    for first, last in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True):
        star_spans.append(TimeSpan(int(first) * frame_seconds, int(last) * frame_seconds))
    events = []
    for syllable in aligned:
        duration = syllable.end_s - syllable.start_s
        if duration < MIN_SYLLABLE_SECONDS - 1e-9:
            events.append(SpliceEvent("short_syllable", syllable.start_s, syllable.end_s))
        if duration > MAX_SYLLABLE_SECONDS + 1e-9:
            events.append(SpliceEvent("long_syllable", syllable.start_s, syllable.end_s))
    groups = []
    start, end = aligned[0].start_s, aligned[0].end_s
    for left, right in zip(aligned, aligned[1:], strict=False):
        if right.start_s - left.end_s > MAX_PAUSE_SECONDS + 1e-9:
            events.append(SpliceEvent("long_pause", left.end_s, right.start_s))
            groups.append(TimeSpan(start, end))
            start = right.start_s
        end = right.end_s
    groups.append(TimeSpan(start, end))
    for span in star_spans:
        if (
            span.start_s >= aligned[0].start_s
            and span.end_s <= aligned[-1].end_s
            and span.end_s - span.start_s > MAX_INTERNAL_STAR_SECONDS + 1e-9
        ):
            events.append(SpliceEvent("long_star", span.start_s, span.end_s))
    return Alignment(tuple(aligned), tuple(star_spans), tuple(groups), tuple(events))


def _decode_audio(audio: bytes | Path) -> np.ndarray:
    if isinstance(audio, Path):
        return load_audio(audio, max_seconds=MAX_AUDIO_SECONDS)
    if not isinstance(audio, bytes):
        raise DecodeError("CTC expects a local audio path or encoded audio bytes")
    try:
        import soundfile as sf
        from scipy.signal import resample_poly

        with sf.SoundFile(io.BytesIO(audio)) as source:
            rate = source.samplerate
            if not 8000 <= rate <= 192000 or not 1 <= source.channels <= 2:
                raise DecodeError("Unsupported CTC audio rate/channels")
            if not source.frames or source.frames / rate > MAX_AUDIO_SECONDS:
                raise DecodeError("Empty or overlong CTC audio")
            waveform = source.read(dtype="float32", always_2d=True).mean(axis=1)
        if not np.isfinite(waveform).all():
            raise DecodeError("Nonfinite CTC audio")
        if rate != SAMPLE_RATE:
            divisor = math.gcd(rate, SAMPLE_RATE)
            waveform = resample_poly(waveform, SAMPLE_RATE // divisor, rate // divisor)
        return np.asarray(waveform, dtype=np.float32)
    except (OSError, ValueError, RuntimeError) as exc:
        raise DecodeError("Cannot decode local CTC audio") from exc


class ForcedAligner:
    """Align the server prompt with one cached model; injected backends keep tests lightweight."""

    version = f"mms-300m-ctc@{REVISION}+voice05-v1-vi-nfd-star-rawspans"

    def __init__(self, models_dir: Path | None = None, *, backend: Any = None) -> None:
        self._backend = backend if backend is not None else TorchCTCBackend(models_dir)
        self._lock = threading.RLock()
        self._preloaded = False
        self._device = "cpu"

    def preload(self, *, models_dir: Path | None = None, device: str = "cpu") -> None:
        """Prepare the local model once before inference; root/device changes require restart."""
        with self._lock:
            if not self._preloaded or models_dir is not None or device != self._device:
                self._backend.preload(models_dir=models_dir, device=device)
                self._preloaded, self._device = True, device

    @staticmethod
    def validate_prompt(prompt: str) -> None:
        """Reject unsupported prompts before decoding or loading the model."""
        if not isinstance(prompt, str):
            raise AlignmentError("Server prompt is required")
        normalized = normalize_text(prompt)
        if not normalized or len(normalized) > MAX_PROMPT_CHARACTERS:
            raise AlignmentError("Server prompt is empty or too long")
        if any(
            not c.isascii() or not (c.isalpha() or c.isspace())
            for c in strip_diacritics(normalized)
        ):
            raise AlignmentError("Prompt contains unsupported Vietnamese alignment characters")

    def align(self, audio: bytes | Path, prompt: str) -> Alignment:
        """Return absolute original-audio times; never VAD-trim or receive an ASR hypothesis."""
        self.validate_prompt(prompt)
        waveform = _decode_audio(audio)
        return self._align_waveform(waveform, prompt)

    def align_samples(self, samples: np.ndarray, sample_rate: int, prompt: str) -> Alignment:
        """Align bounded raw mono float32/16 kHz in RAM without trim or normalization."""
        self.validate_prompt(prompt)
        if (
            type(sample_rate) is not int
            or sample_rate != SAMPLE_RATE
            or not isinstance(samples, np.ndarray)
            or samples.dtype != np.float32
            or samples.ndim != 1
            or not 0 < len(samples) <= MAX_AUDIO_SECONDS * SAMPLE_RATE
            or not np.isfinite(samples).all()
            or np.any(np.abs(samples) > 1)
        ):
            raise DecodeError("CTC expects bounded mono float32 at 16 kHz")
        return self._align_waveform(samples, prompt)

    def _align_waveform(self, waveform: np.ndarray, prompt: str) -> Alignment:
        with self._lock:
            self.preload(device=self._device)
            emissions, stride = self._backend.emissions(waveform)
            return align_emissions(emissions, prompt, self._backend.vocabulary, stride)
