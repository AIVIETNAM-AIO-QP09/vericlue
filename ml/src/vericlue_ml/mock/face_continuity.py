"""Continuity mock, explicitly versioned as mock; never authorizes enrollment."""

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module, ModuleResult
from vericlue_ml.face.continuity import FACE_VOICE_VERSION
from vericlue_ml.mock.detectors import MockDetector


class MockFaceContinuityDetector(MockDetector):
    def __init__(self) -> None:
        super().__init__(Module.FACE_CONTINUITY)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        return (
            super().predict(inp).model_copy(update={"model_version": "mock@" + FACE_VOICE_VERSION})
        )
