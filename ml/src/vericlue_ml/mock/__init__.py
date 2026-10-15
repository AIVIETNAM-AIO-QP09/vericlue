"""Mô-đun giả lập — dùng khi `USE_MOCK_MODELS=true` và trong test."""

from vericlue_ml.mock.detectors import MOCK_DETECTORS, MOCK_VERSION, MockDetector
from vericlue_ml.mock.scenarios import SCENARIOS

__all__ = ["MOCK_DETECTORS", "MOCK_VERSION", "SCENARIOS", "MockDetector"]

from vericlue_ml.common.result import Module
from vericlue_ml.mock.voice_challenge import MockVoiceChallengeDetector

MOCK_DETECTORS[Module.VOICE_CHALLENGE] = MockVoiceChallengeDetector()
