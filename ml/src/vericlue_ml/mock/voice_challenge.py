"""Voice challenge mock with the same Detector interface as the real backend."""

from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector


class MockVoiceChallengeDetector(MockDetector):
    """Reuse the PLAT-03 scenarios without loading ASR dependencies."""

    def __init__(self) -> None:
        super().__init__(Module.VOICE_CHALLENGE)
