"""VOICE-11 raw reading timing from the existing pinned VOICE-05 CTC aligner.

Recipe/source/license are documented in voice/align.py. Align the requested
phrase, never the ASR hypothesis. VAD checks presence only; all timestamps stay
on the original 16 kHz recording clock. Forced spans and provisional duration
flags do not establish correct content, splicing, liveness or a real speaker.
"""

from __future__ import annotations

import math
from pathlib import Path
from time import perf_counter

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Evidence, ModuleResult
from vericlue_ml.voice.align import (
    EXPECTED_FILES,
    MAX_INTERNAL_STAR_SECONDS,
    MAX_PAUSE_SECONDS,
    MAX_SYLLABLE_SECONDS,
    MIN_SYLLABLE_SECONDS,
    REVISION,
    Alignment,
    AlignmentError,
    ForcedAligner,
)
from vericlue_ml.voice.asr import DecodeError, SpeechNotFound, load_audio, speech_bounds
from vericlue_ml.voice.challenge import normalize_text

VERSION = f"mms-300m-ctc@{REVISION}+voice11-timing-v1-raw16k"
MAX_SECONDS = 30
MAX_BYTES = 32 * 1024 * 1024


def timing_result(alignment: Alignment, prompt: str, seconds: float) -> dict:
    """Validate forced spans and describe their timing, without an acceptance rule."""
    syllables = alignment.syllables
    if [s.text for s in syllables] != normalize_text(prompt).split():
        raise AlignmentError("Unexpected aligned syllables")
    spans = (*syllables, *alignment.stars, *alignment.splice_events)
    if not syllables or any(
        not math.isfinite(s.start_s)
        or not math.isfinite(s.end_s)
        or not 0 <= s.start_s < s.end_s <= seconds
        for s in spans
    ):
        raise AlignmentError("Invalid original-clock alignment span")
    gaps = []
    for left, right in zip(syllables, syllables[1:], strict=False):
        if left.end_s > right.start_s:
            raise AlignmentError("Overlapping syllable spans")
        if right.start_s > left.end_s:
            gaps.append(
                {
                    "start_s": left.end_s,
                    "end_s": right.start_s,
                    "duration_s": right.start_s - left.end_s,
                }
            )
    duration = alignment.end_s - alignment.start_s
    return {
        "quality": {
            "diagnostic_only": True,
            "forced_prompt_alignment": True,
            "input_seconds": seconds,
            "aligned_span_seconds": duration,
            "aligned_syllables": len(syllables),
            # Denominator includes pauses inside the forced first-to-last span.
            "syllables_per_second_including_gaps": len(syllables) / duration,
            "longest_gap_seconds": max((g["duration_s"] for g in gaps), default=0),
            "timing_flag_count": len(alignment.splice_events),
        },
        "evidence": [
            Evidence(
                type="segments",
                name="timing_syllables",
                unit="s",
                value=[
                    {
                        "text": s.text,
                        "start_s": s.start_s,
                        "end_s": s.end_s,
                        "duration_s": s.end_s - s.start_s,
                    }
                    for s in syllables
                ],
            ),
            Evidence(type="segments", name="timing_gaps", unit="s", value=gaps),
            Evidence(
                type="segments",
                name="timing_flags",
                unit="s",
                value=[
                    {"kind": s.kind, "start_s": s.start_s, "end_s": s.end_s}
                    for s in alignment.splice_events
                ],
            ),
            Evidence(
                type="text",
                name="provisional_timing_rules",
                value={
                    "pause_gt_s": MAX_PAUSE_SECONDS,
                    "syllable_lt_s": MIN_SYLLABLE_SECONDS,
                    "syllable_gt_s": MAX_SYLLABLE_SECONDS,
                    "internal_star_gt_s": MAX_INTERNAL_STAR_SECONDS,
                    "validated": False,
                },
            ),
        ],
    }


class ReadingTimingDetector:
    """Opt-in timing variant of voice_challenge; always unclear, never a content gate."""

    name = "voice_challenge"
    version = VERSION

    def __init__(
        self, models_dir: Path | None = None, *, aligner: ForcedAligner | None = None
    ) -> None:
        self.aligner = aligner if aligner is not None else ForcedAligner(models_dir)

    def preload(self, *, models_dir: Path | None = None, device: str = "cpu") -> None:
        self.aligner.preload(models_dir=models_dir, device=device)

    def provenance(self) -> dict:
        """Report actual verified assets separately from the pinned expected hashes."""
        backend = self.aligner._backend
        return {
            "model_version": self.version,
            "model_revision": REVISION,
            "expected_model_hashes": dict(EXPECTED_FILES),
            "verified_model_hashes": dict(getattr(backend, "model_hashes", {})),
            "model_loaded": getattr(backend, "model", None) is not None,
            "calibrated": False,
        }

    def predict(self, inp: DetectorInput) -> ModuleResult:
        samples = None
        try:
            ForcedAligner.validate_prompt(inp.metadata.get("prompt"))
            if (
                inp.audio is None
                or not inp.audio.is_file()
                or not 0 < inp.audio.stat().st_size <= MAX_BYTES
            ):
                raise DecodeError("Missing or oversized local audio")
            samples = load_audio(inp.audio, max_seconds=MAX_SECONDS)
            return self.predict_samples(samples, 16000, prompt=inp.metadata.get("prompt"))
        except AlignmentError:
            return self._failure("degraded", "E_LOW_QUALITY", 0)
        except Exception:
            return self._failure("error", "E_DECODE", 0)
        finally:
            if samples is not None:
                samples.fill(0)

    def _failure(self, status: str, code: str, latency: float) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status=status,
            error_code=code,
            gate="unclear",
            latency_ms=latency,
        )

    def predict_samples(
        self, samples: np.ndarray, sample_rate: int, *, prompt: str
    ) -> ModuleResult:
        """Do not mutate caller PCM or replace the ASR/content result with forced text."""
        started = perf_counter()
        try:
            ForcedAligner.validate_prompt(prompt)
            if (
                type(sample_rate) is not int
                or sample_rate != 16000
                or not isinstance(samples, np.ndarray)
                or samples.dtype != np.float32
                or samples.ndim != 1
                or not 0 < len(samples) <= MAX_SECONDS * 16000
                or not np.isfinite(samples).all()
                or np.any(np.abs(samples) > 1)
            ):
                raise DecodeError("Use bounded mono float32/16 kHz")
            speech_bounds(samples)  # Presence only; pass original, untrimmed samples below.
            alignment = self.aligner.align_samples(samples, sample_rate, prompt)
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status="degraded",
                gate="unclear",
                latency_ms=(perf_counter() - started) * 1000,
                **timing_result(alignment, prompt, len(samples) / sample_rate),
            )
        except SpeechNotFound:
            status, code = "not_applicable", "E_LOW_QUALITY"
        except DecodeError:
            status, code = "error", "E_DECODE"
        except AlignmentError:
            status, code = "degraded", "E_LOW_QUALITY"
        except Exception:
            status, code = "error", "E_INTERNAL"
        return self._failure(status, code, (perf_counter() - started) * 1000)
