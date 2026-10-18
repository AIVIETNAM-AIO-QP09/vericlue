"""Danh bạ: chế độ USE_MOCK_MODELS = true / false / mixed."""

import pytest

from vericlue_ml.common import Module
from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.face.pad import FacePadDetector
from vericlue_ml.face.quality import QualityDetector
from vericlue_ml.mock import MOCK_DETECTORS
from vericlue_ml.registry import get_detector, mock_mode, use_mock_models
from vericlue_ml.voice.challenge import VoiceChallengeDetector


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("mixed", "mixed"),
        (" Mixed ", "mixed"),
        ("garbage", False),
        ("", False),
    ],
)
def test_mock_mode_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("USE_MOCK_MODELS", raw)
    assert mock_mode() == expected


def test_mock_mode_default_is_true(monkeypatch):
    monkeypatch.delenv("USE_MOCK_MODELS", raising=False)
    assert mock_mode() is True
    assert use_mock_models() is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("false", False), ("mixed", False), ("garbage", False)],
)
def test_use_mock_models_only_true_when_fully_mock(monkeypatch, raw, expected):
    monkeypatch.setenv("USE_MOCK_MODELS", raw)
    assert use_mock_models() is expected


def test_mixed_picks_real_where_registered(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "mixed")
    assert isinstance(get_detector(Module.FACE_PAD), FacePadDetector)
    assert isinstance(get_detector(Module.VOICE_CHALLENGE), VoiceChallengeDetector)
    assert isinstance(get_detector(Module.FACE_DEEPFAKE), FaceDeepfakeDetector)
    assert isinstance(get_detector(Module.QUALITY), QualityDetector)
    assert get_detector(Module.CHROMAPULSE) is MOCK_DETECTORS[Module.CHROMAPULSE]


def test_mixed_never_raises_for_any_module(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "mixed")
    for module in Module:
        assert get_detector(module) is not None


def test_mixed_passed_directly(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "true")
    assert isinstance(get_detector("face_pad", mock="mixed"), FacePadDetector)
    assert isinstance(get_detector("face_pad", mock=" MIXED "), FacePadDetector)
    assert get_detector("lipsync", mock="mixed") is MOCK_DETECTORS[Module.LIPSYNC]


def test_true_makes_everything_mock(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "true")
    for module in Module:
        assert get_detector(module) is MOCK_DETECTORS[module]
    assert get_detector(Module.FACE_PAD, mock=True) is MOCK_DETECTORS[Module.FACE_PAD]


def test_false_real_or_not_implemented(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    assert isinstance(get_detector(Module.FACE_PAD), FacePadDetector)
    with pytest.raises(NotImplementedError, match="VOICE-05"):
        get_detector(Module.LIPSYNC)
    with pytest.raises(NotImplementedError):
        get_detector(Module.LIPSYNC, mock=False)


def test_explicit_mock_overrides_env(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    assert get_detector(Module.LIPSYNC, mock=True) is MOCK_DETECTORS[Module.LIPSYNC]
    assert get_detector(Module.LIPSYNC, mock="true") is MOCK_DETECTORS[Module.LIPSYNC]
