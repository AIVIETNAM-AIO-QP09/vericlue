"""Bounded whole-recording NES2Net diagnostic (VOICE-13), with no fused verdict.

Reuses voice.nes2net's upstream four-second recipe per window. The non-overlap
grid plus end-anchored tail is OUR protocol, not an upstream evaluated recipe.
No normalization, trimming, concatenation, new weights or threshold fitting.
"""

from __future__ import annotations

import math
from pathlib import Path
from time import perf_counter

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Evidence, ModuleResult
from vericlue_ml.voice.asr import DecodeError
from vericlue_ml.voice.nes2net import (
    MAX_SECONDS,
    SAMPLE_RATE,
    WINDOW_SAMPLES,
    Nes2NetDetector,
    validate_samples,
)
from vericlue_ml.voice.nes2net import (
    VERSION as WINDOW_VERSION,
)

VERSION = WINDOW_VERSION.replace("first4s-v1", "timeline4s-tail-v1")
RECIPE = "4s_grid_end_anchored_tail_repeat_only_if_input_shorter_than_4s_v1"
WINDOWS = "nes2net_windows"


def window_bounds(count: int) -> list[tuple[int, int]]:
    """Cover bounded input in at most eight windows; never repeat a tiny tail."""
    if type(count) is not int or not 0 < count <= MAX_SECONDS * SAMPLE_RATE:
        raise ValueError("Invalid timeline size")
    if count <= WINDOW_SAMPLES:
        return [(0, count)]
    starts = list(range(0, count - WINDOW_SAMPLES + 1, WINDOW_SAMPLES))
    if starts[-1] != count - WINDOW_SAMPLES:
        starts.append(count - WINDOW_SAMPLES)
    return [(start, start + WINDOW_SAMPLES) for start in starts]


def measured_samples(rows: list[dict]) -> int:
    """Union only successfully scored source intervals, excluding repeat/overlap."""
    count = end = 0
    for row in rows:
        if row["result"]["status"] == "degraded":
            count += max(0, row["end_sample"] - max(end, row["start_sample"]))
            end = max(end, row["end_sample"])
    return count


def summary(rows: list[dict], count: int) -> dict:
    """Time coverage describes model execution, never attack detection accuracy."""
    measured = measured_samples(rows)
    return {
        "diagnostic_only": True,
        "frontend_parity_verified": False,
        "calibrated": False,
        "recipe": RECIPE,
        "input_samples": count,
        "input_seconds": count / SAMPLE_RATE,
        "planned_windows": len(rows),
        "measured_windows": sum(row["result"]["status"] == "degraded" for row in rows),
        "low_quality_windows": sum(row["result"]["status"] == "not_applicable" for row in rows),
        "error_windows": sum(row["result"]["status"] == "error" for row in rows),
        "measured_samples": measured,
        "measured_seconds": measured / SAMPLE_RATE,
        "measured_fraction": measured / count,
        "all_source_samples_measured": measured == count,
        "repeated_to_four_seconds": count < WINDOW_SAMPLES,
        "aggregation": "none",
    }


def timeline_status(rows: list[dict]) -> tuple[str, str | None]:
    if any(row["result"]["status"] == "error" for row in rows):
        return "error", "E_INTERNAL"
    if any(row["result"]["status"] == "degraded" for row in rows):
        return "degraded", None
    return "not_applicable", "E_LOW_QUALITY"


def validate_timeline(result: ModuleResult, count: int) -> None:
    """Reject fabricated coverage, skipped windows and non-diagnostic nested results."""
    if (
        result.module != "voice_spoof"
        or result.model_version != VERSION
        or result.gate != "unclear"
        or result.score is not None
        or result.prob_attack is not None
        or not math.isfinite(result.latency_ms)
    ):
        raise ValueError("Invalid timeline result")
    if not result.evidence:
        if result.status != "error" or result.quality:
            raise ValueError("Missing timeline")
        return
    if len(result.evidence) != 1:
        raise ValueError("Unexpected evidence")
    evidence = result.evidence[0]
    bounds = window_bounds(count)
    rows = evidence.value
    if (
        evidence.name != WINDOWS
        or evidence.type != "segments"
        or not isinstance(rows, list)
        or len(rows) != len(bounds)
    ):
        raise ValueError("Invalid windows")
    for row, (start, end) in zip(rows, bounds, strict=True):
        if (
            not isinstance(row, dict)
            or set(row) != {"start_sample", "end_sample", "start_s", "end_s", "result"}
            or type(row["start_sample"]) is not int
            or type(row["end_sample"]) is not int
            or (row["start_sample"], row["end_sample"]) != (start, end)
            or type(row["start_s"]) not in (int, float)
            or type(row["end_s"]) not in (int, float)
            or row["start_s"] != start / SAMPLE_RATE
            or row["end_s"] != end / SAMPLE_RATE
        ):
            raise ValueError("Invalid source interval")
        nested = ModuleResult.model_validate(row["result"])
        if (
            nested.module != "voice_spoof"
            or nested.model_version != WINDOW_VERSION
            or nested.gate != "unclear"
            or nested.prob_attack is not None
            or nested.status not in {"degraded", "error", "not_applicable"}
            or not math.isfinite(nested.latency_ms)
        ):
            raise ValueError("Invalid window diagnostic")
        if nested.status == "degraded":
            logits = {item.name: item.value for item in nested.evidence}
            if (
                set(logits) != {"logit_spoof", "logit_bonafide"}
                or any(
                    type(value) not in (int, float) or not math.isfinite(value)
                    for value in logits.values()
                )
                or nested.score is None
                or not math.isfinite(nested.score)
                or not math.isclose(
                    nested.score,
                    logits["logit_spoof"] - logits["logit_bonafide"],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
            ):
                raise ValueError("Invalid logits")
        elif nested.score is not None or nested.evidence:
            raise ValueError("Unmeasured window has a score")
    if result.quality != summary(rows, count) or (
        result.status,
        result.error_code,
    ) != timeline_status(rows):
        raise ValueError("Invalid coverage summary")


class Nes2NetTimelineDetector:
    """Reuse one cached backend, returning per-window evidence and no clip score."""

    name = "voice_spoof"
    version = VERSION

    def __init__(self, models_dir: Path | None = None, *, backend=None) -> None:
        self.window_detector = Nes2NetDetector(models_dir, backend=backend)
        self.backend = self.window_detector.backend

    def preload(self, *, models_dir: Path | None = None, device: str | None = None) -> None:
        self.window_detector.preload(models_dir=models_dir, device=device)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        """Read bounded local mono 16 kHz audio; wipe our decoded input after use."""
        try:
            samples = Nes2NetDetector._read_file(inp.audio)
        except DecodeError:
            return self._failure("E_DECODE", 0)
        except Exception:
            return self._failure("E_INTERNAL", 0)
        try:
            return self.predict_samples(samples)
        finally:
            samples.fill(0)

    def _failure(self, code: str, latency: float) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status="error",
            gate="unclear",
            error_code=code,
            latency_ms=latency,
        )

    def predict_samples(self, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> ModuleResult:
        """Never mutate caller PCM; bad windows stay visible without erasing good ones."""
        started = perf_counter()
        try:
            validate_samples(samples, sample_rate)
        except DecodeError:
            return self._failure("E_DECODE", (perf_counter() - started) * 1000)
        rows = []
        for start, end in window_bounds(len(samples)):
            result = self.window_detector.predict_samples(samples[start:end], sample_rate)
            rows.append(
                {
                    "start_sample": start,
                    "end_sample": end,
                    "start_s": start / SAMPLE_RATE,
                    "end_s": end / SAMPLE_RATE,
                    "result": result.to_contract(),
                }
            )
        status, code = timeline_status(rows)
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status=status,
            gate="unclear",
            error_code=code,
            quality=summary(rows, len(samples)),
            evidence=[Evidence(type="segments", name=WINDOWS, value=rows)],
            latency_ms=(perf_counter() - started) * 1000,
        )
