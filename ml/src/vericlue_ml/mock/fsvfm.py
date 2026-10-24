"""FS-VFM PAD mock for the opt-in diagnostic factory."""

from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector


class MockFsvfmPadDetector(MockDetector):
    def __init__(self):
        super().__init__(Module.FACE_PAD)

    def preload(self, **kwargs):
        return None

    def predict_frames(self, inp, frames):
        return self.predict(inp)
