"""Mô-đun giả lập — dùng khi `USE_MOCK_MODELS=true` và trong test."""

from vericlue_ml.mock.detectors import MOCK_DETECTORS, MOCK_VERSION, MockDetector
from vericlue_ml.mock.scenarios import SCENARIOS

__all__ = ["MOCK_DETECTORS", "MOCK_VERSION", "SCENARIOS", "MockDetector"]

from vericlue_ml.common.result import Module
from vericlue_ml.mock.face_match import MockFaceMatchDetector
from vericlue_ml.mock.gaze import MockGazeDetector
from vericlue_ml.mock.head_turn import MockHeadTurnDetector
from vericlue_ml.mock.voice_challenge import MockVoiceChallengeDetector

MOCK_DETECTORS[Module.VOICE_CHALLENGE] = MockVoiceChallengeDetector()
MOCK_DETECTORS[Module.GAZE_TRACKING] = MockGazeDetector()
MOCK_DETECTORS[Module.HEAD_TURN] = MockHeadTurnDetector()
MOCK_DETECTORS[Module.FACE_MATCH] = MockFaceMatchDetector()
