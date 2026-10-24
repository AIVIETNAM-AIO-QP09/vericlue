"""Opt-in real checkpoint test on synthetic silence; no recording or accuracy claim."""

import os
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.voice.asr import SpeechNotFound
from vericlue_ml.voice.qwen_asr import QwenASR


@pytest.mark.slow
def test_qwen_native_cpu_generation_and_silence_gate(tmp_path):
    root = os.getenv("QWEN_ASR_MODELS_DIR")
    if not root:
        pytest.skip("Set QWEN_ASR_MODELS_DIR and use the separate Qwen runtime")
    import soundfile as sf
    import torch

    provider = QwenASR(Path(root))
    provider.preload()
    model = provider._model
    assert str(model.device) == "cpu" and model.dtype == torch.float32
    provider.preload()
    assert provider._model is model and len(provider.model_hashes) == 7
    generated = []
    original = model.generate

    def generate(**kwargs):
        output = original(**kwargs)
        generated.append(tuple(output.shape))
        return output

    model.generate = generate
    # Deliberately bypass VAD here to exercise real processor/model generation on zero audio.
    # This is not a speech-recognition correctness test; the public file path below keeps VAD.
    try:
        text = provider._infer(np.zeros(16000, np.float32), token_budget=64)
        assert isinstance(text, str)
    except SpeechNotFound:
        pass
    assert len(generated) == 1
    path = tmp_path / "synthetic-silence.wav"
    sf.write(path, np.zeros(16000, np.float32), 16000, subtype="PCM_16")
    with pytest.raises(SpeechNotFound):
        provider.transcribe(path)
    with pytest.raises(SpeechNotFound):
        provider.transcribe_samples(np.zeros(48000, np.float32), 48000)
    assert len(generated) == 1
