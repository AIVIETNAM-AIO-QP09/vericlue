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


@pytest.mark.slow
def test_existing_local_tts_transcripts_are_unchanged_by_generation_guards(monkeypatch):
    if os.getenv("RUN_VOICE04_TTS_REGRESSION") != "1":
        pytest.skip("Opt in to replay existing local TTS fixtures; never creates audio.")
    manifest_path = os.getenv("VOICE04_TTS_MANIFEST")
    model_root = os.getenv("MODELS_DIR")
    if not manifest_path or not model_root:
        pytest.skip("Set VOICE04_TTS_MANIFEST and MODELS_DIR.")
    for dependency in ("torch", "transformers", "soundfile", "webrtcvad"):
        pytest.importorskip(dependency)
    from vericlue_ml.voice.asr import PhoWhisperASR
    from vericlue_ml.voice.challenge import normalize_text

    manifest = Path(manifest_path)
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(rows) == 4 and {row["case"] for row in rows} == {
        "correct",
        "wrong",
        "near_syllable",
        "near_tone",
    }
    provider = PhoWhisperASR(Path(model_root), device="cpu")
    provider.preload()
    original_generate = provider._model.generate
    legacy = False

    def generate(**kwargs):
        if legacy:
            for key in ("max_new_tokens", "no_repeat_ngram_size", "stopping_criteria"):
                kwargs.pop(key)
        return original_generate(**kwargs)

    monkeypatch.setattr(provider._model, "generate", generate)
    for row in rows:
        audio = manifest.parent / row["path"]
        count = len(normalize_text(row["expected"]).split())
        legacy = True
        before = provider.transcribe(audio, expected_syllable_count=count)
        legacy = False
        after = provider.transcribe(audio, expected_syllable_count=count)
        assert before.strip() and after == before, f"Transcript changed in local case {row['case']}"
