"""Opt-in NES2Net checkpoint through a persistent child; synthetic tone only, no microphone."""

import importlib.metadata
import os
import threading
from pathlib import Path

import numpy as np
import pytest


@pytest.mark.slow
def test_qwen_runtime_communicates_with_real_nes2net_runtime_without_dependency_change():
    python, models = os.getenv("NES2NET_WORKER_PYTHON"), os.getenv("NES2NET_MODELS_DIR")
    if not python or not models:
        pytest.skip("Set NES2NET_WORKER_PYTHON and NES2NET_MODELS_DIR in the Qwen runtime")
    from vericlue_ml.eval.nes2net_client import Nes2NetClient

    before = importlib.metadata.version("transformers")
    assert before == "5.13.0"
    time = np.arange(64000, dtype=np.float32) / 16000
    phase = 2 * np.pi * (120 * time + 3 * np.sin(2 * np.pi * time))
    samples = (
        (0.18 * np.sin(phase) + 0.08 * np.sin(2 * phase) + 0.04 * np.sin(3 * phase))
        * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * time))
    ).astype(np.float32)
    client = Nes2NetClient(Path(python), Path(models), timeout=180)
    process = None
    try:
        first = client.predict_samples(samples, cancelled=threading.Event())
        assert first["worker_available"] and first["model_loaded"]
        process = client._process
        second = client.predict_samples(samples, cancelled=threading.Event())
        assert client._process is process and second["model_loaded"]
        assert first["runtime"]["transformers"] == "4.57.6"
        assert second["result"]["status"] == "degraded"
        assert second["result"]["gate"] == "unclear"
        assert "prob_attack" not in second["result"]
        assert first["result"]["score"] == second["result"]["score"]
        assert first["pcm_float32_sha256"] == second["pcm_float32_sha256"]
        assert first["request_id"] != second["request_id"]
        assert second["load_report"]["missing_keys"] == []
        assert second["load_report"]["unexpected_keys"] == []
        assert second["verified_model_hashes"] == second["expected_model_hashes"]
        assert importlib.metadata.version("transformers") == before
    finally:
        client.close()
        if process is not None:
            process.wait(timeout=10)
