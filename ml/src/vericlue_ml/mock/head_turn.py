"""Head motion mock; a positive gate only describes the requested motion sequence."""

from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector


class MockHeadTurnDetector(MockDetector):
    def __init__(self) -> None:
        super().__init__(Module.HEAD_TURN)
