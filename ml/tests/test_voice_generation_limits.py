"""Bounded ASR must reject truncated prefixes before decoding or challenge matching."""

from __future__ import annotations

import copy
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Status
from vericlue_ml.voice import asr
from vericlue_ml.voice.challenge import VoiceChallengeDetector


@pytest.mark.parametrize(
    "count,expected", [(None, 128), (1, 24), (10, 96), (20, 176), (30, 256), (1000, 256)]
)
def test_generation_budget_uses_only_numeric_count_and_has_an_absolute_cap(count, expected):
    assert asr.generation_token_budget(count) == expected


@pytest.mark.parametrize("count", [True, False, 0, -1, 1.5, "10", [], np.int64(10)])
def test_generation_budget_rejects_invalid_counts(count):
    with pytest.raises(ValueError, match="positive integer"):
        asr.generation_token_budget(count)


class LoopingModel:
    """Autoregressively grow raw decoder IDs, then mimic Whisper removing EOS."""

    def __init__(self, mode):
        self.mode = mode
        self.calls = []
        self.steps = []
        self.generation_config = SimpleNamespace(
            max_new_tokens=None,
            no_repeat_ngram_size=0,
            forced_decoder_ids=[[1, 123]],
            nested={"preserve": [1, 2]},
        )

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        budget = kwargs["max_new_tokens"]
        assert kwargs["no_repeat_ngram_size"] == 8
        prefix, generated = [50258, 50318, 50359], []
        for step in range(budget):
            token = 50257 if self.mode == "short" and step == 2 else 100 + step % 7
            if self.mode == "eos_at_cap" and step == budget - 1:
                token = 50257
            generated.append(token)
            raw = np.array([prefix + generated], dtype=np.int64)
            self.steps.append(raw.copy())
            # HF calls every criterion even when its own EOS/length criterion is done.
            assert all(criterion(raw, None) is False for criterion in kwargs["stopping_criteria"])
            if token == 50257:
                break
        if generated[-1] == 50257:
            generated.pop()
        return np.array([generated], dtype=np.int64)


@pytest.fixture
def fake_recognizer(monkeypatch):
    torch = ModuleType("torch")
    torch.inference_mode = nullcontext
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setattr(asr, "load_audio", lambda path: np.zeros(16000, dtype=np.float32))
    monkeypatch.setattr(asr, "trim_silence", lambda audio, **kwargs: audio)

    def make(mode="short", transcript="xin chào"):
        model = LoopingModel(mode)
        processor_calls, decode_calls = [], []

        class Processor:
            def __call__(self, audio, **kwargs):
                processor_calls.append((audio.copy(), kwargs))
                return {"input_features": "synthetic-features", "attention_mask": "synthetic-mask"}

            def batch_decode(self, output, **kwargs):
                decode_calls.append((output.copy(), kwargs))
                return [transcript]

        backend = asr.PhoWhisperASR(models_dir=Path("unopened-models"), device="cpu")
        backend._model, backend._processor = model, Processor()
        return backend, model, processor_calls, decode_calls

    return make


@pytest.mark.parametrize("mode", ["loop", "eos_at_cap"])
def test_cap_reached_raises_before_decoding_even_if_decoder_would_return_the_correct_prefix(
    fake_recognizer, mode
):
    backend, model, _, decode_calls = fake_recognizer(mode, transcript="xin chào")
    with pytest.raises(asr.ASRError):
        backend.transcribe(Path("unopened.wav"), expected_syllable_count=2)
    assert len(model.steps) == 32
    assert model.calls[0]["stopping_criteria"][0].exhausted
    assert decode_calls == []


@pytest.mark.parametrize("mode", ["loop", "eos_at_cap"])
def test_truncated_correct_prefix_cannot_pass_voice_challenge(fake_recognizer, mode):
    backend, model, _, decode_calls = fake_recognizer(mode, transcript="xin chào")
    result = VoiceChallengeDetector(backend).predict(
        DetectorInput(audio=Path("unopened.wav"), metadata={"prompt": "xin chào"})
    )
    assert result.status == Status.ERROR
    assert result.error_code == ErrorCode.E_INTERNAL
    assert result.gate != "pass"
    assert result.score is result.prob_attack is None
    assert model.calls[0]["max_new_tokens"] == asr.generation_token_budget(2)
    assert decode_calls == []


def test_valid_short_transcript_is_unchanged_and_never_supplies_expected_text_to_asr(
    fake_recognizer,
):
    backend, model, processor_calls, decode_calls = fake_recognizer(
        transcript="  Xin chào, tôi xác nhận!  "
    )
    original_config = copy.deepcopy(vars(model.generation_config))
    assert backend.transcribe(Path("unopened.wav"), expected_syllable_count=6) == (
        "Xin chào, tôi xác nhận!"
    )
    assert backend.version.endswith("voice04-v2")
    assert vars(model.generation_config) == original_config
    assert len(decode_calls) == 1
    kwargs = model.calls[0]
    assert set(kwargs) == {
        "input_features",
        "attention_mask",
        "language",
        "task",
        "condition_on_prev_tokens",
        "return_timestamps",
        "max_new_tokens",
        "no_repeat_ngram_size",
        "stopping_criteria",
    }
    assert kwargs["language"] == "vi" and kwargs["task"] == "transcribe"
    assert kwargs["condition_on_prev_tokens"] is False
    assert kwargs["return_timestamps"] is True
    assert not kwargs["stopping_criteria"][0].exhausted
    assert processor_calls[0][1] == {
        "sampling_rate": 16000,
        "return_tensors": "pt",
        "return_attention_mask": True,
        "truncation": False,
    }


def test_cap_failure_does_not_poison_a_later_complete_transcription(fake_recognizer):
    backend, model, _, decode_calls = fake_recognizer("loop")
    with pytest.raises(asr.ASRError):
        backend.transcribe(Path("unopened.wav"))
    model.mode = "short"
    assert backend.transcribe(Path("unopened.wav")) == "xin chào"
    first, second = [call["stopping_criteria"][0] for call in model.calls]
    assert first is not second
    assert first.exhausted and not second.exhausted
    assert len(decode_calls) == 1


def test_observer_resets_per_chunk_instead_of_accumulating_complete_short_chunks():
    observer = asr._TokenBudgetObserver(4)
    for prefix_length in (3, 2, 3):
        for generated in range(1, 4):
            assert observer(np.zeros((1, prefix_length + generated)), None) is False
            assert not observer.exhausted


def test_observer_exhaustion_stays_sticky_after_a_chunk_or_fallback_reset():
    observer = asr._TokenBudgetObserver(4)
    for generated in range(1, 5):
        assert observer(np.zeros((1, 3 + generated)), None) is False
    assert observer.exhausted
    for generated in range(1, 3):
        assert observer(np.zeros((1, 3 + generated)), None) is False
        assert observer.exhausted


def test_optional_hf_stopping_criteria_calls_observer_even_when_default_length_stops():
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from transformers.generation.stopping_criteria import MaxLengthCriteria, StoppingCriteriaList

    observer = asr._TokenBudgetObserver(3)
    criteria = StoppingCriteriaList([MaxLengthCriteria(max_length=6), observer])
    for length in (4, 5, 6):
        stopped = criteria(torch.zeros((1, length), dtype=torch.long), None)
        assert bool(stopped.item()) is (length == 6)
    assert observer.exhausted


def test_optional_hf_eightgram_masks_a_real_loop_and_preserves_valid_short_repetition():
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from transformers.generation.logits_process import NoRepeatNGramLogitsProcessor

    processor = NoRepeatNGramLogitsProcessor(8)
    scores = torch.zeros((1, 64))
    repeated = torch.tensor([[11, 12, 13, 14, 15, 16, 17, 18, 11, 12, 13, 14, 15, 16, 17]])
    masked = processor(repeated, scores)
    assert torch.isneginf(masked[0, 18])
    assert torch.isfinite(masked[0, 19])
    valid_short_repetition = torch.tensor([[1, 2, 3, 4, 5, 6, 1, 2, 3]])
    assert torch.equal(processor(valid_short_repetition, scores), scores)
    assert torch.isneginf(NoRepeatNGramLogitsProcessor(4)(valid_short_repetition, scores)[0, 4])
