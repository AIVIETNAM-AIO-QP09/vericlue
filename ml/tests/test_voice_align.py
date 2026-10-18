"""VOICE-05 CTC tests use synthetic frame emissions; no weights, network, or dataset."""

from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from vericlue_ml.voice import align
from vericlue_ml.voice.asr import DecodeError

VOCABULARY = {"<blank>": 0, "a": 1, "b": 2, "e": 3, "m": 4, "t": 5}


def emissions(*runs: tuple[str, int]) -> np.ndarray:
    """Synthetic sharp posteriors include slight nonzero probability for every class."""
    labels = [VOCABULARY[token] for token, length in runs for _ in range(length)]
    logits = np.full((len(labels), len(VOCABULARY)), -12.0)
    logits[np.arange(len(labels)), labels] = 0
    return logits - np.logaddexp.reduce(logits, axis=1, keepdims=True)


def ordinary(gap: int = 5) -> np.ndarray:
    return emissions(
        ("<blank>", 5), ("b", 5), ("a", 10), ("<blank>", gap), ("m", 5), ("e", 10), ("<blank>", 5)
    )


def test_vietnamese_prompt_preserves_syllables_and_absolute_audio_time() -> None:
    result = align.align_emissions(ordinary(), "Bà mẹ!", VOCABULARY)
    assert [s.text for s in result.syllables] == ["bà", "mẹ"]
    assert result.syllables[0].start_s == pytest.approx(0.1)
    assert result.syllables[0].end_s == pytest.approx(0.4)
    assert result.syllables[1].start_s == pytest.approx(0.5)
    assert result.syllables[1].end_s == pytest.approx(0.8)
    assert result.start_s == pytest.approx(0.1)
    assert result.end_s == pytest.approx(0.8)
    assert result.aligned_segments == (align.TimeSpan(0.1, 0.8),)
    assert result.splice_events == ()


def test_spliced_gap_is_visible_and_splits_contiguous_syncnet_segments() -> None:
    result = align.align_emissions(ordinary(gap=60), "bà mẹ", VOCABULARY)
    assert {event.kind for event in result.splice_events} >= {"long_pause", "long_star"}
    assert len(result.aligned_segments) == 2
    assert [segment.start_s for segment in result.aligned_segments] == pytest.approx([0.1, 1.6])
    assert [segment.end_s for segment in result.aligned_segments] == pytest.approx([0.4, 1.9])
    pause = next(event for event in result.splice_events if event.kind == "long_pause")
    assert pause.start_s == pytest.approx(0.4)
    assert pause.end_s == pytest.approx(1.6)


def test_long_wildcard_preserves_unprompted_interior_speech() -> None:
    values = emissions(
        ("<blank>", 5), ("b", 5), ("a", 10), ("t", 70), ("m", 5), ("e", 10), ("<blank>", 5)
    )
    result = align.align_emissions(values, "bà mẹ", VOCABULARY)
    assert any(event.kind == "long_star" for event in result.splice_events)
    assert any(span.end_s - span.start_s > 1 for span in result.stars)


def test_edge_silence_does_not_count_as_internal_star_or_prompt_pause() -> None:
    values = emissions(("<blank>", 90), ("b", 5), ("a", 10), ("<blank>", 90))
    result = align.align_emissions(values, "bà", VOCABULARY)
    assert result.start_s == pytest.approx(1.8)
    assert result.end_s == pytest.approx(2.1)
    assert result.splice_events == ()


def test_missing_prompt_syllable_produces_short_forced_span() -> None:
    values = emissions(("<blank>", 5), ("b", 5), ("a", 10), ("<blank>", 20))
    result = align.align_emissions(values, "bà mẹ", VOCABULARY)
    missing = result.syllables[1]
    assert missing.text == "mẹ"
    assert missing.end_s - missing.start_s < align.MIN_SYLLABLE_SECONDS
    assert any(
        event.kind == "short_syllable" and event.start_s == missing.start_s
        for event in result.splice_events
    )


@pytest.mark.parametrize(("length", "kind"), [(1, "short_syllable"), (70, "long_syllable")])
def test_syllable_duration_rules_use_posterior_supported_boundaries(length, kind) -> None:
    values = emissions(("<blank>", 5), ("b", 1), ("a", length), ("<blank>", 5))
    result = align.align_emissions(values, "bà", VOCABULARY)
    assert result.syllables[0].end_s - result.syllables[0].start_s == pytest.approx(
        (length + 1) * align.CTC_FRAME_SECONDS
    )
    assert any(event.kind == kind for event in result.splice_events)


def test_ctc_repeated_characters_require_an_intervening_blank() -> None:
    values = emissions(("<blank>", 3), ("a", 5), ("<blank>", 3), ("a", 5), ("<blank>", 3))
    result = align.align_emissions(values, "aa", VOCABULARY)
    assert result.syllables[0].start_s == pytest.approx(0.06)
    assert result.syllables[0].end_s == pytest.approx(0.32)
    with pytest.raises(align.AlignmentError, match="Not enough"):
        align.align_emissions(values[:4], "aaa", VOCABULARY)


@pytest.mark.parametrize("prompt", ["", "!!!", "猫", "a" * 513])
def test_empty_overlong_or_unsupported_prompts_fail_closed(prompt: str) -> None:
    with pytest.raises(align.AlignmentError):
        align.align_emissions(ordinary(), prompt, VOCABULARY)


@pytest.mark.parametrize("invalid", [np.array([]), np.zeros((0, 6)), np.full((10, 6), np.nan)])
def test_bad_emissions_fail_closed(invalid: np.ndarray) -> None:
    with pytest.raises(align.AlignmentError):
        align.align_emissions(invalid, "bà", VOCABULARY)


def test_blank_is_fixed_zero_not_the_processor_padding_token() -> None:
    invalid_vocabulary = {"a": 0, "<blank>": 1, "b": 2, "e": 3, "m": 4, "t": 5}
    with pytest.raises(align.AlignmentError):
        align.align_emissions(ordinary(), "bà mẹ", invalid_vocabulary)


def test_every_required_local_asset_is_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = {}
    for name in align.EXPECTED_FILES:
        data = f"synthetic asset {name}".encode()
        (tmp_path / name).write_bytes(data)
        expected[name] = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(align, "EXPECTED_FILES", expected)
    align._verify_model_files(tmp_path)
    for name in expected:
        original = (tmp_path / name).read_bytes()
        (tmp_path / name).write_bytes(b"corrupted")
        with pytest.raises(align.AlignmentLoadError, match="SHA-256"):
            align._verify_model_files(tmp_path)
        (tmp_path / name).write_bytes(original)
    (tmp_path / "vocab.json").unlink()
    with pytest.raises(align.AlignmentLoadError, match="Missing"):
        align._verify_model_files(tmp_path)


def test_missing_assets_prevent_transformers_or_torch_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"torch", "transformers"}:
            raise AssertionError("Unverified model must not load")
        return real_import(name, *args, **kwargs)

    backend = align.TorchCTCBackend(tmp_path)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(align.AlignmentLoadError):
        backend.preload()
    assert backend.model is None
    with pytest.raises(align.AlignmentLoadError, match="previously failed"):
        backend.preload()


def test_pinned_asset_hashes_match_tracked_manifest() -> None:
    repo = Path(__file__).resolve().parents[2]
    manifest = yaml.safe_load((repo / "models/manifest.yaml").read_text(encoding="utf-8"))
    model = next(item for item in manifest["models"] if item["id"] == "ctc-aligner")
    assert model["source"]["revision"] == align.REVISION
    assert {item["path"]: item["sha256"] for item in model["files"]} == align.EXPECTED_FILES


@pytest.mark.parametrize("missing_keys", [[], ["ctc_head.weight"]])
def test_hf_loader_is_offline_strict_and_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_keys: list[str]
) -> None:
    calls = []
    vocabulary = {"<blank>": 0, **{f"token-{i}": i for i in range(1, 31)}}
    processor = SimpleNamespace(tokenizer=SimpleNamespace(get_vocab=lambda: vocabulary))
    model = SimpleNamespace(config=SimpleNamespace(inputs_to_logits_ratio=320, vocab_size=31))
    model.to = lambda device: model
    model.eval = lambda: model

    class Processor:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append(("processor", path, kwargs))
            return processor

    class Model:
        @staticmethod
        def from_pretrained(path, **kwargs):
            calls.append(("model", path, kwargs))
            return model, {"missing_keys": missing_keys}

    torch = SimpleNamespace(float32="float32", set_num_threads=lambda count: None)
    transformers = SimpleNamespace(AutoModelForCTC=Model, AutoProcessor=Processor)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    verified = []
    monkeypatch.setattr(align, "_verify_model_files", lambda directory: verified.append(directory))
    backend = align.TorchCTCBackend(tmp_path)
    if missing_keys:
        with pytest.raises(align.AlignmentLoadError):
            backend.preload()
        assert backend.model is None
        return
    backend.preload()
    backend.preload()
    assert verified == [tmp_path.resolve() / "ctc-aligner"]
    assert [name for name, _, _ in calls] == ["processor", "model"]
    for _, path, kwargs in calls:
        assert Path(path) == verified[0]
        assert kwargs["local_files_only"] is True
        assert kwargs["trust_remote_code"] is False
    model_kwargs = calls[1][2]
    assert model_kwargs["use_safetensors"] is True
    assert model_kwargs["output_loading_info"] is True
    assert backend.vocabulary["<blank>"] == 0
    with pytest.raises(align.AlignmentLoadError, match="another root/device"):
        backend.preload(models_dir=tmp_path / "other")


def test_aligner_uses_server_prompt_once_loaded_without_asr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Backend:
        vocabulary = VOCABULARY

        def __init__(self):
            self.preloads = []
            self.waveforms = []

        def preload(self, **kwargs):
            self.preloads.append(kwargs)

        def emissions(self, waveform):
            self.waveforms.append(waveform)
            return ordinary(), 0.02

    waveform = np.ones(16000, dtype=np.float32)
    monkeypatch.setattr(align, "_decode_audio", lambda path: waveform)
    backend = Backend()
    aligner = align.ForcedAligner(backend=backend)
    first = aligner.align(tmp_path / "audio.wav", "bà mẹ")
    second = aligner.align(tmp_path / "audio.wav", "ba me")
    assert [s.text for s in first.syllables] == ["bà", "mẹ"]
    assert [s.text for s in second.syllables] == ["ba", "me"]
    assert len(backend.preloads) == 1
    assert all(value is waveform for value in backend.waveforms)


@pytest.mark.parametrize("prompt", ["", "猫", "a" * 513])
def test_invalid_server_prompt_fails_before_decode_or_model_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prompt: str
) -> None:
    def forbidden_decode(audio):
        raise AssertionError("Invalid server prompts must fail before media/model work")

    monkeypatch.setattr(align, "_decode_audio", forbidden_decode)
    aligner = align.ForcedAligner(backend=object())
    with pytest.raises(align.AlignmentError):
        aligner.align(tmp_path / "audio.wav", prompt)


def test_encoded_audio_is_bounded_decoded_and_resampled_without_model() -> None:
    sf = pytest.importorskip("soundfile")

    stream = io.BytesIO()
    sf.write(stream, np.ones((8000, 2), dtype=np.float32) * 0.25, 8000, format="WAV")
    waveform = align._decode_audio(stream.getvalue())
    assert waveform.dtype == np.float32
    assert waveform.shape == (16000,)
    assert waveform[100:-100].mean() == pytest.approx(0.25, abs=0.001)
    with pytest.raises(DecodeError):
        align._decode_audio(b"invalid audio")
