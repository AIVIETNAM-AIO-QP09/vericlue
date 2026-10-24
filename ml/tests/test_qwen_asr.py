"""Qwen diagnostics: fake native backend and synthetic local bytes, no checkpoints."""

import contextlib
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from test_voice_matching import fake_match_libraries as fake_match_libraries

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.registry import get_detector, get_qwen_voice_challenge
from vericlue_ml.voice.asr import ASRError, DecodeError, SpeechNotFound
from vericlue_ml.voice.qwen_asr import (
    REVISION,
    RUNTIME_FILES,
    QwenASR,
    QwenVoiceChallengeDetector,
    extract_transcript,
)


@pytest.mark.parametrize(
    "raw",
    [
        "plain text",
        "language English<asr_text>hello",
        "language Vietnamese<asr_text><asr_text>x",
        "language Vietnamese<asr_text>hello<tool>",
    ],
)
def test_invalid_envelope_or_language_never_becomes_a_transcript(raw):
    with pytest.raises(ASRError):
        extract_transcript(raw)


def test_transcript_keeps_repeated_words_instead_of_repairing_them():
    text = "tôi xác nhận " * 25
    assert extract_transcript("language Vietnamese<asr_text>" + text) == text.strip()
    with pytest.raises(SpeechNotFound):
        extract_transcript("language None<asr_text>")


def local_provider(monkeypatch, tmp_path):
    folder = tmp_path / "models/qwen3-asr-06b-hf"
    folder.mkdir(parents=True)
    hashes = {}
    for name in RUNTIME_FILES:
        path = folder / name
        path.write_bytes(("synthetic fixture: " + name).encode())
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    config = {
        "revision": REVISION,
        "sha256": hashes,
        "cpu_threads": 4,
        "model_subdir": "qwen3-asr-06b-hf",
    }
    source = tmp_path / "config.yaml"
    source.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setenv("QWEN_ASR_CONFIG", str(source))
    return QwenASR(folder.parent), folder


def test_all_runtime_files_are_verified_before_native_import(monkeypatch, tmp_path):
    provider, folder = local_provider(monkeypatch, tmp_path)
    calls = []
    provider._load_native = lambda root: calls.append(root) or (object(), object())
    provider.preload()
    provider.preload()
    assert calls == [folder] and set(provider.model_hashes) == RUNTIME_FILES
    with pytest.raises(ASRError):
        provider.preload(models_dir=tmp_path / "other")


@pytest.mark.parametrize("name", sorted(RUNTIME_FILES))
def test_each_tampered_file_prevents_loading_and_failure_stays_latched(monkeypatch, tmp_path, name):
    provider, folder = local_provider(monkeypatch, tmp_path)
    original = (folder / name).read_bytes()
    (folder / name).write_bytes(b"changed")
    provider._load_native = lambda root: pytest.fail("Integrity failure must precede native load")
    with pytest.raises(ASRError):
        provider.preload()
    (folder / name).write_bytes(original)
    with pytest.raises(ASRError):
        provider.preload()


def test_model_change_during_load_is_detected(monkeypatch, tmp_path):
    provider, folder = local_provider(monkeypatch, tmp_path)

    def load(_root):
        (folder / "tokenizer.json").write_text("changed", encoding="utf-8")
        return object(), object()

    provider._load_native = load
    with pytest.raises(ASRError):
        provider.preload()
    assert provider._model is None


def fake_native(monkeypatch, tmp_path, *, tokens=(20, 21, 99), raw=None):
    provider, _ = local_provider(monkeypatch, tmp_path)
    calls = []

    class Inputs(dict):
        def to(self, *args):
            calls.append(("to", args))
            return self

    def request(**kwargs):
        calls.append(("request", kwargs))
        return Inputs(input_ids=np.array([[11, 12]], dtype=int))

    def generate(**kwargs):
        calls.append(("generate", kwargs))
        return np.array([[11, 12, *tokens]])

    provider._processor = SimpleNamespace(
        apply_transcription_request=request,
        decode=lambda ids, **kwargs: (
            raw if raw is not None else "language Vietnamese<asr_text>tôi xác nhận"
        ),
    )
    provider._model = SimpleNamespace(
        generate=generate, generation_config=SimpleNamespace(eos_token_id=[99])
    )
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            inference_mode=contextlib.nullcontext,
            float32="synthetic-float32",
        ),
    )
    return provider, calls


def test_native_request_has_audio_and_language_but_no_expected_text(monkeypatch, tmp_path):
    provider, calls = fake_native(monkeypatch, tmp_path)
    audio = np.zeros(16000, np.float32)
    assert provider._infer(audio, token_budget=128) == "tôi xác nhận"
    request = next(value for kind, value in calls if kind == "request")
    assert request["audio"] is audio
    assert set(request) == {"audio", "language", "sampling_rate", "return_tensors"}
    assert request["language"] == "Vietnamese" and request["sampling_rate"] == 16000
    generation = next(value for kind, value in calls if kind == "generate")
    assert generation["do_sample"] is False and generation["max_new_tokens"] == 128


@pytest.mark.parametrize("tokens,budget", [((20, 21), 128), ((20, 99), 2), ((), 128)])
def test_incomplete_generation_never_accepts_a_correct_looking_prefix(
    monkeypatch, tmp_path, tokens, budget
):
    provider, _ = fake_native(monkeypatch, tmp_path, tokens=tokens)
    with pytest.raises(ASRError):
        provider._infer(np.zeros(16000, np.float32), token_budget=budget)


def test_invalid_samples_are_rejected_before_native_inference(monkeypatch, tmp_path):
    provider, calls = fake_native(monkeypatch, tmp_path)
    for audio in (np.zeros((16000, 2)), np.zeros(100), np.full(16000, float("nan"))):
        with pytest.raises(ASRError):
            provider._infer(audio, token_budget=128)
    assert not calls


def test_count_only_budget_and_silence_do_not_leak_prompt_or_load_model(monkeypatch, tmp_path):
    from vericlue_ml.voice import qwen_asr

    provider, _ = local_provider(monkeypatch, tmp_path)
    path = tmp_path / "clip.wav"
    path.write_bytes(b"synthetic audio")
    monkeypatch.setattr(qwen_asr, "load_audio", lambda *args, **kwargs: np.zeros(16000, np.float32))
    monkeypatch.setattr(qwen_asr, "trim_silence", lambda samples, **kwargs: samples)
    calls = []
    provider._infer = lambda audio, **kwargs: calls.append(kwargs) or "recognized"
    assert provider.transcribe(path, expected_syllable_count=12) == "recognized"
    assert calls == [{"token_budget": 112}]
    with pytest.raises(ValueError):
        provider.transcribe(path, expected_syllable_count=True)
    monkeypatch.setattr(qwen_asr, "trim_silence", lambda *args, **kwargs: np.zeros(100))
    with pytest.raises(SpeechNotFound):
        provider.transcribe(path)
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["correct", "wrong", "silent", "decode", "backend"])
def test_content_gate_is_separate_from_voice_authenticity(kind, fake_match_libraries):
    def transcribe(path, *, expected_syllable_count):
        assert expected_syllable_count == 3
        if kind == "silent":
            raise SpeechNotFound("none")
        if kind == "decode":
            raise DecodeError("bad input")
        if kind == "backend":
            raise ASRError("private path")
        return "tôi xác nhận" if kind == "correct" else "hôm nay trời đẹp"

    detector = QwenVoiceChallengeDetector(
        SimpleNamespace(version="synthetic@unit", transcribe=transcribe)
    )
    result = detector.predict(
        DetectorInput(
            audio=Path("unused.wav"),
            metadata={"prompt": "tôi xác nhận"},
            signals={"prompt": "client text is ignored"},
        )
    )
    assert result.prob_attack is None and result.quality["diagnostic_only"] is True
    assert result.gate == (
        "pass" if kind == "correct" else "fail" if kind == "wrong" else "unclear"
    )
    if kind in ("decode", "backend"):
        assert result.status == "error" and "private" not in result.model_dump_json()


def test_factory_preserves_existing_phowhisper_and_mock_selection():
    assert isinstance(get_qwen_voice_challenge(), QwenVoiceChallengeDetector)
    assert get_qwen_voice_challenge(mock=True) is get_detector("voice_challenge", mock=True)
    assert get_detector("voice_challenge", mock=False).version.startswith("phowhisper-")


def test_cli_source_change_invalidates_even_a_matching_result(monkeypatch, tmp_path):
    from vericlue_ml.common.result import ModuleResult
    from vericlue_ml.eval import qwen_voice

    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"before")
    expected = tmp_path / "expected.txt"
    expected.write_text("tôi xác nhận", encoding="utf-8")
    output = tmp_path / "report.json"
    provider = SimpleNamespace(
        version="synthetic@unit",
        config={"revision": "synthetic", "sha256": {}},
        model_hashes={},
        _model=None,
    )

    def predict(_inp):
        audio.write_bytes(b"after")
        return ModuleResult(
            module="voice_challenge",
            model_version="synthetic@unit",
            status="ok",
            gate="pass",
            latency_ms=0,
        )

    monkeypatch.setattr(qwen_voice, "QwenASR", lambda *_args: provider)
    monkeypatch.setattr(
        qwen_voice, "QwenVoiceChallengeDetector", lambda *_args: SimpleNamespace(predict=predict)
    )
    monkeypatch.setattr(qwen_voice.importlib.metadata, "version", lambda _name: "synthetic")
    assert (
        qwen_voice.main(
            [
                "--audio",
                str(audio),
                "--expected-text-file",
                str(expected),
                "--models-dir",
                str(tmp_path / "models"),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["result"]["error_code"] == "E_INTEGRITY"
    assert payload["result"]["gate"] == "unclear" and payload["sample_count"] == 1


@pytest.mark.parametrize("target", ["audio", "expected", "model"])
def test_cli_does_not_overwrite_inputs_or_model_files(tmp_path, target):
    from vericlue_ml.eval.qwen_voice import main

    audio = tmp_path / "clip.wav"
    expected = tmp_path / "expected.txt"
    audio.write_bytes(b"synthetic input")
    expected.write_text("tôi xác nhận", encoding="utf-8")
    models = tmp_path / "models"
    output = (
        audio if target == "audio" else expected if target == "expected" else models / "config.json"
    )
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--audio",
                str(audio),
                "--expected-text-file",
                str(expected),
                "--models-dir",
                str(models),
                "--output",
                str(output),
            ]
        )
    assert exc.value.code == 2
    assert audio.read_bytes() == b"synthetic input"
    assert expected.read_text(encoding="utf-8") == "tôi xác nhận"
