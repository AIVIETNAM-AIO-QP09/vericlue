"""Mock for the server-timed video identity variant; no media or model access."""

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module, ModuleResult
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION
from vericlue_ml.mock.detectors import MockDetector


class MockVideoFaceMatchDetector(MockDetector):
    def __init__(self) -> None:
        super().__init__(Module.FACE_MATCH)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        return (
            super().predict(inp).model_copy(update={"model_version": "mock@" + VIDEO_MATCH_VERSION})
        )
