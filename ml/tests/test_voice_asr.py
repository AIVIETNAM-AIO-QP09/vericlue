"""Offline ASR contract and fail-closed tests; no weights or audio fixtures in Git."""

from __future__ import annotations

import inspect
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.voice import asr
from vericlue_ml.voice.challenge import VoiceChallengeDetector


class FakeASR:
    version = "mock@voice-unit"

    def __init__(self, result="xin chào", error=None):
        self.result, self.error, self.calls = result, error, []

    def transcribe(self, audio_path):
        self.calls.append(audio_path)
        if self.error:
            raise self.error
        return self.result


def test_asr_interface_cannot_receive_challenge():
    assert list(inspect.signature(asr.PhoWhisperASR.transcribe).parameters) == [
        "self",
        "audio_path",
    ]
    with pytest.raises(TypeError):
        asr.PhoWhisperASR().transcribe(Path("x.wav"), prompt="expected")


@pytest.mark.parametrize(
    "error",
    [
        asr.ASRError("unavailable"),
        asr.DecodeError("bad"),
        OSError("missing"),
        ImportError("dependency"),
        RuntimeError("provider"),
        TypeError("unexpected"),
    ],
)
def test_provider_errors_never_pass(error):
    detector = VoiceChallengeDetector(FakeASR(error=error))
    result = detector.predict(DetectorInput(audio=Path("x.wav"), metadata={"prompt": "xin chào"}))
    assert result.status == "error"
    assert result.gate != "pass"
    assert result.prob_attack is None


def test_silence_never_passes():
    result = VoiceChallengeDetector(FakeASR(error=asr.SpeechNotFound())).predict(
        DetectorInput(audio=Path("x.wav"), metadata={"prompt": "xin chào"})
    )
    assert result.status == "not_applicable" and result.gate != "pass"


def test_missing_prompt_does_not_call_asr():
    backend = FakeASR()
    result = VoiceChallengeDetector(backend).predict(DetectorInput(audio=Path("x.wav")))
    assert result.status == "error" and backend.calls == []


def test_missing_audio_is_decode_error():
    result = VoiceChallengeDetector(FakeASR()).predict(
        DetectorInput(metadata={"prompt": "xin chào"})
    )
    assert result.error_code == "E_DECODE" and result.gate != "pass"


def test_expected_text_stays_in_matcher(monkeypatch):
    backend = FakeASR("xin chào")
    import vericlue_ml.voice.challenge as challenge

    monkeypatch.setattr(
        challenge,
        "compare_transcripts",
        lambda expected, actual, **kwargs: SimpleNamespace(
            matched=expected == actual, syllable_wer=0.0, unaccented_similarity=1.0
        ),
    )
    result = VoiceChallengeDetector(backend).predict(
        DetectorInput(audio=Path("x.wav"), metadata={"prompt": "xin chào"})
    )
    assert backend.calls == [Path("x.wav")]
    assert result.status == "ok" and result.gate == "pass"
    assert result.prob_attack is None


def test_mismatch_is_ok_fail_not_infrastructure_error(monkeypatch):
    import vericlue_ml.voice.challenge as challenge

    monkeypatch.setattr(
        challenge,
        "compare_transcripts",
        lambda *args, **kwargs: SimpleNamespace(
            matched=False, syllable_wer=1.0, unaccented_similarity=0.0
        ),
    )
    result = VoiceChallengeDetector(FakeASR("wrong")).predict(
        DetectorInput(audio=Path("x.wav"), metadata={"prompt": "expected"})
    )
    assert result.status == "ok" and result.gate == "fail"
    assert result.error_code == "E_CHALLENGE_MISMATCH"


def test_generation_has_no_expected_prompt_and_model_loads_once(monkeypatch):
    backend = asr.PhoWhisperASR()
    calls = []

    class Processor:
        def __call__(self, audio, **kwargs):
            return {"input_features": "features", "attention_mask": "mask"}

        def batch_decode(self, output, **kwargs):
            return ["xin chào"]

    class Model:
        def generate(self, **kwargs):
            calls.append(kwargs)
            return "tokens"

    def load():
        backend._model, backend._processor = Model(), Processor()

    monkeypatch.setattr(backend, "_load", load)
    monkeypatch.setattr(asr, "load_audio", lambda path: np.zeros(16000))
    monkeypatch.setattr(asr, "trim_silence", lambda audio, **kwargs: audio)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    assert backend.transcribe(Path("a.wav")) == "xin chào"
    assert backend.transcribe(Path("b.wav")) == "xin chào"
    assert (
        calls
        == [
            dict(
                input_features="features",
                attention_mask="mask",
                language="vi",
                task="transcribe",
                condition_on_prev_tokens=False,
                return_timestamps=True,
            )
        ]
        * 2
    )


def test_missing_weights_never_downloads(tmp_path):
    backend = asr.PhoWhisperASR(tmp_path)
    with pytest.raises(asr.ASRError):
        backend._load()


def test_local_loader_cpu_and_reuses_weights(tmp_path, monkeypatch):
    directory = tmp_path / "phowhisper"
    directory.mkdir()
    (directory / "pytorch_model.bin").write_bytes(b"fixture-not-real-weights")
    calls = []

    class Model:
        def to(self, device):
            assert device == "cpu"
            return self

        def eval(self):
            return self

    def loader(path, **kwargs):
        calls.append(kwargs)
        assert path == str(directory)
        return Model()

    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(float32="fp32", set_num_threads=lambda count: None)
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            WhisperProcessor=SimpleNamespace(from_pretrained=loader),
            WhisperForConditionalGeneration=SimpleNamespace(from_pretrained=loader),
        ),
    )
    backend = asr.PhoWhisperASR(tmp_path)
    backend._load()
    backend._load()
    assert len(calls) == 2
    assert all(c["local_files_only"] and c["trust_remote_code"] is False for c in calls)
    assert calls[1]["weights_only"] is True


def test_vad_preserves_internal_gaps_and_valid_frame_size(monkeypatch):
    responses = iter([False] * 20 + [True] + [False] * 40 + [True] + [False] * 20)

    class VAD:
        def __init__(self, mode):
            assert mode == 1

        def is_speech(self, block, rate):
            assert len(block) == 640 and rate == 16000
            return next(responses)

    monkeypatch.setitem(sys.modules, "webrtcvad", SimpleNamespace(Vad=VAD))
    audio = np.ones(82 * 320, dtype=np.float32)
    result = asr.trim_silence(audio)
    assert len(result) == 62 * 320  # from frame10 through frame71, internal silence retained.


def test_vad_silence_and_partial_frames(monkeypatch):
    class VAD:
        def __init__(self, mode):
            pass

        def is_speech(self, block, rate):
            assert len(block) == 640
            return False

    monkeypatch.setitem(sys.modules, "webrtcvad", SimpleNamespace(Vad=VAD))
    with pytest.raises(asr.SpeechNotFound):
        asr.trim_silence(np.zeros(321))


def test_decoder_resamples_stereo_and_rejects_invalid_audio(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "soundfile",
        SimpleNamespace(
            info=lambda path: SimpleNamespace(samplerate=8000, channels=2, frames=8000),
            read=lambda *args, **kwargs: (np.ones((8000, 2), dtype=np.float32) * 0.1, 8000),
        ),
    )
    assert asr.load_audio(Path("fake.wav")).shape == (16000,)
    monkeypatch.setitem(
        sys.modules,
        "soundfile",
        SimpleNamespace(
            info=lambda path: SimpleNamespace(samplerate=8000, channels=2, frames=8000),
            read=lambda *args, **kwargs: (np.full((8000, 2), np.nan), 8000),
        ),
    )
    with pytest.raises(asr.DecodeError):
        asr.load_audio(Path("fake.wav"))


def test_registry_reuses_real_detector_without_loading_weights():
    from vericlue_ml.registry import get_detector

    a = get_detector("voice_challenge", mock=False)
    assert get_detector("voice_challenge", mock=False) is a
    assert a.asr._model is None
    assert get_detector("voice_challenge", mock=True).version.startswith("mock@")
