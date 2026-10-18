"""PR27 revisions: repo-relative roots, explicit VAD bounds and API preload injection."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module, Status
from vericlue_ml.voice import antispoof as anti
from vericlue_ml.voice import asr


@pytest.mark.parametrize(
    "choice", ["default", "environment", "explicit-relative", "explicit-absolute"]
)
def test_model_root_is_independent_of_process_working_directory(tmp_path, monkeypatch, choice):
    checkout = tmp_path / "checkout"
    source = checkout / "ml/src/vericlue_ml/voice/antispoof.py"
    source.parent.mkdir(parents=True)
    source.write_text("# simulated source location", encoding="utf-8")
    monkeypatch.setattr(anti, "__file__", str(source))
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("MODELS_DIR", raising=False)
    explicit = None
    expected = checkout / "models"
    if choice == "environment":
        monkeypatch.setenv("MODELS_DIR", "shared/model-files")
        expected = checkout / "shared/model-files"
    elif choice == "explicit-relative":
        monkeypatch.setenv("MODELS_DIR", "wrong-env-root")
        explicit = Path("explicit/model-files")
        expected = checkout / explicit
    elif choice == "explicit-absolute":
        monkeypatch.setenv("MODELS_DIR", "wrong-env-root")
        explicit = tmp_path / "absolute-models"
        expected = explicit
    assert anti._root(explicit) == expected.resolve()


def test_explicit_speech_bounds_produce_original_file_timestamps_without_pointer_inference(
    monkeypatch,
):
    original = np.linspace(-0.5, 0.5, 96000, dtype=np.float32)
    monkeypatch.setattr(anti, "load_audio", lambda _: original.copy())
    monkeypatch.setattr(anti, "speech_bounds", lambda _audio, **_kwargs: (16000, 80000))
    seen = []

    def backend(audio):
        seen.append(audio.copy())
        return np.array([0.0, 0.0])

    result = anti.AntiDeepfakeDetector(backend=backend).predict(
        DetectorInput(audio=Path("fake.wav"))
    )
    assert result.status == Status.OK
    assert result.quality["duration_s"] == 6
    assert result.quality["speech_duration_s"] == 4
    assert result.quality["trim_start_s"] == 1
    windows = next(e.value for e in result.evidence if e.name == "window_scores")
    assert windows[0]["start_s"] == 1 and windows[0]["end_s"] == 5
    assert len(seen) == 1 and seen[0].shape == (64000,)


def test_shared_vad_bounds_keep_padding_and_trim_returns_identical_slice(monkeypatch):
    class FakeVad:
        def __init__(self, mode):
            assert mode == 1
            self.index = 0

        def is_speech(self, pcm, rate):
            assert rate == 16000 and len(pcm) == 640
            result = 20 <= self.index < 25
            self.index += 1
            return result

    monkeypatch.setitem(sys.modules, "webrtcvad", SimpleNamespace(Vad=FakeVad))
    audio = np.linspace(-0.5, 0.5, 60 * 320, dtype=np.float32)
    assert asr.speech_bounds(audio) == (3200, 11200)
    trimmed = asr.trim_silence(audio)
    np.testing.assert_array_equal(trimmed, audio[3200:11200])


def test_backend_preload_binds_explicit_root_once_and_refuses_repointing(tmp_path, monkeypatch):
    monkeypatch.setattr(anti, "_configuration", lambda: {"model_subdir": "custom-anti"})
    backend = anti.TorchAntiDeepfakeBackend(models_dir=tmp_path / "initial")
    loaded = []

    def fake_load():
        loaded.append(backend.model_dir)
        backend.model = object()

    monkeypatch.setattr(backend, "_load", fake_load)
    configured = tmp_path / "configured"
    backend.preload(models_dir=configured)
    backend.preload(models_dir=configured)
    assert loaded == [configured.resolve() / "custom-anti"]
    assert backend.models_dir == configured.resolve()
    with pytest.raises(anti.ModelLoadError):
        backend.preload(models_dir=tmp_path / "different")
    assert backend.model_dir == configured.resolve() / "custom-anti"
    assert len(loaded) == 1


def test_detector_preload_forwards_explicit_models_root_without_inference(tmp_path):
    seen = []

    class Backend:
        def preload(self, *, models_dir=None):
            seen.append(models_dir)

        def __call__(self, _audio):
            raise AssertionError("preload must not infer")

    detector = anti.AntiDeepfakeDetector(backend=Backend())
    target = tmp_path / "configured"
    detector.preload(models_dir=target)
    detector.preload(models_dir=target)
    # Explicit roots are forwarded every time for backend validation; loading itself
    # is cached by the backend and covered separately above.
    assert seen == [target, target]


def test_mixed_registry_contains_both_real_face_pad_and_voice_spoof():
    from vericlue_ml.face.pad import FacePadDetector
    from vericlue_ml.mock.detectors import MockDetector
    from vericlue_ml.registry import get_detector

    assert isinstance(get_detector(Module.FACE_PAD, mock="mixed"), FacePadDetector)
    assert isinstance(get_detector(Module.VOICE_SPOOF, mock="mixed"), anti.AntiDeepfakeDetector)
    assert isinstance(get_detector(Module.LIPSYNC, mock="mixed"), MockDetector)
