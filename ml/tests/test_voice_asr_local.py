"""Opt-in integration: local model + local audio, never download weights."""

import importlib.util
import json
import os
from pathlib import Path

import pytest


@pytest.mark.slow
def test_local_phowhisper_transcribes_audio():
    model_root = os.getenv("MODELS_DIR")
    data_root = os.getenv("DATA_DIR")
    if not model_root or not data_root:
        pytest.skip("Set MODELS_DIR and DATA_DIR for local integration.")
    if not (Path(model_root) / "phowhisper/pytorch_model.bin").is_file():
        pytest.skip("PhoWhisper weights missing.")
    if any(
        importlib.util.find_spec(name) is None
        for name in ("torch", "transformers", "soundfile", "webrtcvad")
    ):
        pytest.skip("Install the optional voice extra.")
    manifest = Path(data_root) / "raw/vimd/selected_manifest.json"
    if not manifest.is_file():
        pytest.skip("Local ViMD missing.")
    from vericlue_ml.voice.asr import PhoWhisperASR

    rows = json.loads(manifest.read_text(encoding="utf-8"))
    assert PhoWhisperASR().transcribe(manifest.parent / rows[0]["path"]).strip()
