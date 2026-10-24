"""LIVE-02 mock follows the common deterministic scenario protocol."""

from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector


class MockGazeDetector(MockDetector):
    def __init__(self) -> None:
        super().__init__(Module.GAZE_TRACKING)
