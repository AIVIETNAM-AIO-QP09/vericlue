"""Opt-in real local processor regression; synthetic PCM, no model weights or inference."""

import hashlib
import importlib.metadata
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.slow
def test_local_processor_preserves_official_prefill_and_rejects_generated_controls(monkeypatch):
    root = os.getenv("VERICLUE_QWEN_PROCESSOR_MODELS")
    if not root:
        pytest.skip("Set VERICLUE_QWEN_PROCESSOR_MODELS and use the separate Qwen runtime")

    import numpy as np
    import torch
    from transformers import AutoProcessor

    from vericlue_ml.voice.asr import ASRError
    from vericlue_ml.voice.qwen_asr import QwenASR

    assert importlib.metadata.version("transformers") == "5.13.0"
    config = Path(__file__).resolve().parents[1] / "configs/qwen3_asr.yaml"
    monkeypatch.setenv("QWEN_ASR_CONFIG", str(config))
    provider = QwenASR(Path(root))
    folder = provider.models_dir / provider.config["model_subdir"]
    # Verify only small runtime files. Do not open or load model.safetensors.
    for name in (
        "chat_template.jinja",
        "tokenizer.json",
        "tokenizer_config.json",
        "processor_config.json",
    ):
        with (folder / name).open("rb") as handle:
            assert (
                hashlib.file_digest(handle, "sha256").hexdigest() == provider.config["sha256"][name]
            )
    processor = AutoProcessor.from_pretrained(
        str(folder), local_files_only=True, trust_remote_code=False
    )
    provider._processor = processor
    transcript = "mẫu thử nội bộ"
    suffix = processor.tokenizer.encode(transcript, add_special_tokens=False)
    eos = processor.tokenizer.convert_tokens_to_ids("<|im_end|>")
    control = processor.tokenizer.convert_tokens_to_ids("<|audio_pad|>")
    assert eos in processor.tokenizer.all_special_ids
    assert control in processor.tokenizer.all_special_ids
    received = []
    emit_control = False

    def generate(**inputs):
        ids = inputs["input_ids"]
        assert ids.dtype == torch.int64  # BatchFeature.to must not cast token IDs to float.
        assert inputs["input_features"].dtype == torch.float32
        assert torch.isfinite(inputs["input_features"]).all()
        assert inputs["input_features_mask"].sum() > 0
        prompt = processor.tokenizer.decode(ids[0], skip_special_tokens=False)
        assert prompt.startswith("<|im_start|>system\n<|im_end|>\n<|im_start|>user\n")
        assert prompt.endswith("<|im_start|>assistant\nlanguage Vietnamese<asr_text>")
        assert transcript not in prompt
        assert inputs["do_sample"] is False and inputs["num_beams"] == 1
        received.append(ids.shape[1])
        generated = ([control] if emit_control else []) + suffix + [eos]
        return torch.cat((ids, torch.tensor([generated], dtype=ids.dtype)), dim=1)

    provider._model = SimpleNamespace(
        generate=generate, generation_config=SimpleNamespace(eos_token_id=[eos])
    )
    audio = (0.1 * np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)).astype(np.float32)
    assert provider._infer(audio, token_budget=64) == transcript
    # The real tokenizer would hide this generated control token when decoding;
    # the wrapper must reject it before skip_special_tokens can erase it.
    emit_control = True
    with pytest.raises(ASRError, match="Unexpected ASR control tokens"):
        provider._infer(audio, token_budget=64)
    assert len(received) == 2 and received[0] == received[1]
