"""VOICE-01 anti-spoof wrapper: CPU fake backend, no model weights or network."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Module, Status
from vericlue_ml.voice import antispoof as anti
from vericlue_ml.voice.asr import DecodeError, SpeechNotFound


class FakeBackend:
    def __init__(self, outputs=None, failure=None):
        self.outputs = outputs or [[0.0, 0.0]]
        self.failure = failure
        self.inputs = []
        self.preloads = 0

    def preload(self):
        self.preloads += 1

    def __call__(self, waveform):
        self.inputs.append(np.array(waveform, copy=True))
        if self.failure:
            raise self.failure
        return np.asarray(self.outputs[min(len(self.inputs) - 1, len(self.outputs) - 1)])


@pytest.fixture
def decoded(monkeypatch):
    def configure(waveform, trim=None):
        monkeypatch.setattr(anti, "load_audio", lambda _path: np.array(waveform, copy=True))
        monkeypatch.setattr(anti, "trim_silence", trim or (lambda values, **_kwargs: values))

    return configure


def predict(detector):
    return detector.predict(DetectorInput(audio=Path("synthetic.wav")))


@pytest.mark.parametrize(
    "length,expected",
    [
        (16000, [0]),
        (32000, [0]),
        (63999, [0]),
        (64000, [0]),
        (64001, [0, 1]),
        (65600, [0, 1600]),
        (80000, [0, 16000]),
        (81000, [0, 16000, 17000]),
        (112000, [0, 16000, 32000, 48000]),
    ],
)
def test_window_starts_four_seconds_one_second_hop_with_anchored_tail(length, expected):
    assert anti.window_starts(length) == expected


def test_short_audio_window_preserves_samples_without_padding():
    audio = np.arange(24000, dtype=np.float32)
    windows = anti.make_windows(audio)
    assert len(windows) == 1
    start, end, values = windows[0]
    assert (start, end) == (0.0, 1.5)
    np.testing.assert_array_equal(values, audio)
    assert values.shape == (24000,)


def test_long_windows_use_anchored_tail_without_duplicate_or_lost_samples():
    audio = np.arange(81000, dtype=np.float32)
    windows = anti.make_windows(audio)
    assert [(start, end) for start, end, _ in windows] == [(0.0, 4.0), (1.0, 5.0), (1.0625, 5.0625)]
    assert all(values.shape == (64000,) for _, _, values in windows)
    np.testing.assert_array_equal(windows[-1][2], audio[-64000:])


def test_window_helpers_accept_explicit_window_and_hop():
    assert anti.window_starts(10, window=6, hop=3) == [0, 3, 4]


def test_layer_norm_matches_upstream_eps_and_does_not_mutate_source(decoded):
    waveform = np.tile(np.array([0.1, 0.3, 0.5, 0.7], dtype=np.float32), 4000)
    original = waveform.copy()
    decoded(waveform)
    backend = FakeBackend()
    detector = anti.AntiDeepfakeDetector(backend=backend, device="cpu")
    result = predict(detector)
    assert result.status == Status.OK
    assert backend.inputs[0].dtype == np.float32
    expected = (waveform - waveform.mean()) / np.sqrt(waveform.var() + 1e-5)
    np.testing.assert_allclose(backend.inputs[0], expected, rtol=2e-5, atol=2e-6)
    np.testing.assert_array_equal(waveform, original)


def test_mean_logit_pooling_then_softmax_uses_fake_class_zero(decoded):
    decoded(np.linspace(-0.4, 0.4, 80000, dtype=np.float32))
    backend = FakeBackend(outputs=[[0.0, 0.0], [2.0, 0.0]])
    result = predict(anti.AntiDeepfakeDetector(backend=backend))
    assert result.module == Module.VOICE_SPOOF and result.status == Status.OK
    assert result.score == pytest.approx(1 / (1 + np.exp(-1)))
    assert result.prob_attack is None
    assert not result.model_version.startswith("mock@")
    evidence = next(item for item in result.evidence if item.name == "window_scores")
    assert evidence.type == "timeseries"
    assert len(evidence.value) == 2
    assert evidence.value[0]["start_s"] == 0 and evidence.value[0]["end_s"] == 4
    assert evidence.value[1]["start_s"] == 1 and evidence.value[1]["end_s"] == 5
    assert evidence.value[0]["score"] == pytest.approx(0.5)
    assert evidence.value[1]["score"] == pytest.approx(1 / (1 + np.exp(-2)))
    assert evidence.value[1]["logits"] == [2.0, 0.0]


@pytest.mark.parametrize("length", [0, 15999])
def test_less_than_one_second_is_not_applicable_before_loading(decoded, length):
    decoded(np.zeros(length, dtype=np.float32))
    backend = FakeBackend()
    result = predict(anti.AntiDeepfakeDetector(backend=backend))
    assert result.status == Status.NOT_APPLICABLE and result.prob_attack is None
    assert backend.preloads == 0 and backend.inputs == []


def test_less_than_one_second_after_vad_is_not_applicable(decoded):
    decoded(
        np.zeros(32000, dtype=np.float32),
        trim=lambda _values, **_kwargs: np.zeros(15999, dtype=np.float32),
    )
    backend = FakeBackend()
    result = predict(anti.AntiDeepfakeDetector(backend=backend))
    assert result.status == Status.NOT_APPLICABLE
    assert backend.preloads == 0 and backend.inputs == []


def test_silence_is_not_applicable_without_loading_backend(decoded):
    def no_speech(_values, **_kwargs):
        raise SpeechNotFound("synthetic silence")

    decoded(np.zeros(32000, dtype=np.float32), trim=no_speech)
    backend = FakeBackend()
    result = predict(anti.AntiDeepfakeDetector(backend=backend))
    assert result.status == Status.NOT_APPLICABLE and result.prob_attack is None
    assert backend.preloads == 0 and backend.inputs == []


def test_exactly_one_second_is_not_padded_to_four_seconds(decoded):
    decoded(np.linspace(-0.5, 0.5, 16000, dtype=np.float32))
    backend = FakeBackend()
    result = predict(anti.AntiDeepfakeDetector(backend=backend))
    assert result.status == Status.OK
    assert [len(values) for values in backend.inputs] == [16000]


def test_missing_audio_is_decode_error():
    backend = FakeBackend()
    result = anti.AntiDeepfakeDetector(backend=backend).predict(DetectorInput())
    assert result.status == Status.ERROR and result.error_code == ErrorCode.E_DECODE
    assert result.prob_attack is None and backend.inputs == []


def test_decode_error_never_loads_backend(monkeypatch):
    def fail(_path):
        raise DecodeError("synthetic undecodable file")

    monkeypatch.setattr(anti, "load_audio", fail)
    backend = FakeBackend()
    result = predict(anti.AntiDeepfakeDetector(backend=backend))
    assert result.status == Status.ERROR and result.error_code == ErrorCode.E_DECODE
    assert backend.preloads == 0 and backend.inputs == []


@pytest.mark.parametrize(
    "failure", [RuntimeError("secret backend failure"), OSError("offline missing")]
)
def test_backend_failure_is_internal_error_without_probability(decoded, failure):
    decoded(np.ones(32000, dtype=np.float32))
    result = predict(anti.AntiDeepfakeDetector(backend=FakeBackend(failure=failure)))
    assert result.status == Status.ERROR and result.error_code == ErrorCode.E_INTERNAL
    assert result.prob_attack is None and result.score is None
    assert "secret backend failure" not in result.model_dump_json()


@pytest.mark.parametrize(
    "logits", [[float("nan"), 0.0], [0.0, float("inf")], [1.0], [[1.0, 0.0]], [1.0, 2.0, 3.0]]
)
def test_invalid_logits_never_produce_usable_probability(decoded, logits):
    decoded(np.ones(32000, dtype=np.float32))
    result = predict(anti.AntiDeepfakeDetector(backend=FakeBackend(outputs=[logits])))
    assert result.status == Status.ERROR and result.error_code == ErrorCode.E_INTERNAL
    assert result.score is None and result.prob_attack is None


def test_preload_happens_once_across_explicit_preload_and_multiple_predictions(decoded):
    decoded(np.ones(32000, dtype=np.float32))
    backend = FakeBackend()
    detector = anti.AntiDeepfakeDetector(backend=backend)
    detector.preload()
    detector.preload()
    assert predict(detector).status == Status.OK
    assert predict(detector).status == Status.OK
    assert backend.preloads == 1 and len(backend.inputs) == 2


def test_callable_without_preload_is_supported_and_softmax_is_stable(decoded):
    decoded(np.ones(16000, dtype=np.float32))
    result = predict(
        anti.AntiDeepfakeDetector(backend=lambda _waveform: np.array([10000.0, 9999.0]))
    )
    assert result.status == Status.OK
    assert result.score == pytest.approx(1 / (1 + np.exp(-1)))
    assert result.prob_attack is None


def test_real_registry_factory_is_cached_without_loading_weights(monkeypatch):
    from vericlue_ml import registry

    factory = registry._REAL_FACTORIES[Module.VOICE_SPOOF]
    assert hasattr(factory, "cache_clear"), "real anti-spoof factory must cache its instance"
    factory.cache_clear()
    constructed = []

    class StubDetector:
        name, version = "voice_spoof", "synthetic@factory"

        def __init__(self):
            constructed.append(self)

    monkeypatch.setattr(anti, "AntiDeepfakeDetector", StubDetector)
    try:
        first = registry.get_detector(Module.VOICE_SPOOF, mock=False)
        second = registry.get_detector(Module.VOICE_SPOOF, mock=False)
        assert first is second
        assert constructed == [first]
        mock = registry.get_detector(Module.VOICE_SPOOF, mock=True)
        assert mock.version.startswith("mock@") and mock is not first
    finally:
        factory.cache_clear()


def fake_soundfile(monkeypatch, audio, rate=16000, *, metadata=None):
    values = np.asarray(audio, dtype=np.float32)
    info = metadata or SimpleNamespace(
        samplerate=rate, channels=values.shape[1], frames=len(values)
    )
    calls = []

    def read(path, *, dtype, always_2d):
        calls.append((path, dtype, always_2d))
        return values.copy(), rate

    monkeypatch.setitem(
        sys.modules, "soundfile", SimpleNamespace(info=lambda _path: info, read=read)
    )
    return calls


def test_local_decoder_averages_stereo_channels_as_float32_without_resampling(monkeypatch):
    audio = np.array([[0.1, 0.3], [-0.6, 0.2], [0.5, 0.7]], dtype=np.float32)
    calls = fake_soundfile(monkeypatch, audio)
    decoded = anti.load_audio(Path("local.wav"))
    assert decoded.dtype == np.float32 and decoded.shape == (3,)
    np.testing.assert_allclose(decoded, audio.mean(axis=1))
    assert calls == [(Path("local.wav"), "float32", True)]


def test_local_decoder_preserves_mono_samples(monkeypatch):
    audio = np.array([[0.2], [-0.4], [0.6]], dtype=np.float32)
    fake_soundfile(monkeypatch, audio)
    np.testing.assert_array_equal(anti.load_audio(Path("mono.wav")), audio[:, 0])


@pytest.mark.parametrize(
    "rate,channels,frames",
    [
        (7999, 1, 16000),
        (192001, 1, 16000),
        (16000, 0, 16000),
        (16000, 3, 16000),
        (16000, 1, 0),
        (16000, 1, 16000 * 121),
    ],
)
def test_decoder_rejects_invalid_metadata_before_reading(monkeypatch, rate, channels, frames):
    info = SimpleNamespace(samplerate=rate, channels=channels, frames=frames)
    calls = fake_soundfile(monkeypatch, np.zeros((4, 1)), metadata=info)
    with pytest.raises(DecodeError):
        anti.load_audio(Path("invalid.wav"))
    assert not calls


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_decoder_rejects_nonfinite_samples(monkeypatch, invalid):
    fake_soundfile(monkeypatch, np.array([[0.1], [invalid]], dtype=np.float32))
    with pytest.raises(DecodeError):
        anti.load_audio(Path("invalid-samples.wav"))


def test_decoder_uses_upstream_torchaudio_resample_after_mono_mean(monkeypatch):
    audio = np.array([[0.1, 0.3], [-0.6, 0.2], [0.5, 0.7]], dtype=np.float32)
    fake_soundfile(monkeypatch, audio, rate=8000)
    captured = []

    class FakeTensor:
        def __init__(self, array):
            self.array = array

        def numpy(self):
            return self.array

    def resample(tensor, original_rate, new_rate):
        captured.append((tensor.array.copy(), original_rate, new_rate))
        return FakeTensor(np.repeat(tensor.array, 2))

    torch = ModuleType("torch")
    torch.from_numpy = FakeTensor
    torchaudio = ModuleType("torchaudio")
    torchaudio.__path__ = []
    functional = ModuleType("torchaudio.functional")
    functional.resample = resample
    torchaudio.functional = functional
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "torchaudio", torchaudio)
    monkeypatch.setitem(sys.modules, "torchaudio.functional", functional)
    decoded = anti.load_audio(Path("stereo-8khz.wav"))
    assert len(captured) == 1 and captured[0][1:] == (8000, 16000)
    np.testing.assert_allclose(captured[0][0], audio.mean(axis=1))
    np.testing.assert_array_equal(decoded, np.repeat(audio.mean(axis=1), 2))
