"""Opt-in functional CTC test on synthetic tones; no accuracy or biometric evaluation."""

import os
from pathlib import Path

import numpy as np
import pytest


@pytest.mark.slow
def test_ctc_timing_runs_in_qwen_runtime_and_caches_verified_model():
    root = os.getenv("READING_TIMING_MODELS_DIR")
    if not root:
        pytest.skip("Set READING_TIMING_MODELS_DIR in the separate Qwen runtime")
    from vericlue_ml.voice.reading_timing import ReadingTimingDetector

    detector = ReadingTimingDetector(Path(root))
    silent = detector.predict_samples(np.zeros(16000, np.float32), 16000, prompt="bà mẹ")
    assert silent.status == "not_applicable" and not detector.provenance()["model_loaded"]
    times = np.arange(64000, dtype=np.float32) / 16000
    phase = 2 * np.pi * (120 * times + 3 * np.sin(2 * np.pi * times))
    samples = (
        (0.18 * np.sin(phase) + 0.08 * np.sin(2 * phase) + 0.04 * np.sin(3 * phase))
        * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * times))
    ).astype(np.float32)
    first = detector.predict_samples(samples, 16000, prompt="bà mẹ")
    cached = detector.aligner._backend.model
    second = detector.predict_samples(samples, 16000, prompt="bà mẹ")
    assert cached is detector.aligner._backend.model and cached is not None
    assert first.status == second.status == "degraded" and second.gate == "unclear"
    assert second.score is second.prob_attack is None and not second.is_usable
    assert first.quality == second.quality and first.evidence == second.evidence
    metadata = detector.provenance()
    assert metadata["verified_model_hashes"] == metadata["expected_model_hashes"]
