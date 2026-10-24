"""Deterministic identity comparison mock for backend integration tests."""

from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector


class MockFaceMatchDetector(MockDetector):
    def __init__(self) -> None:
        super().__init__(Module.FACE_MATCH)
