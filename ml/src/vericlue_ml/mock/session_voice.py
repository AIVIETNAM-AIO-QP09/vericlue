"""Session voice adapters have ordinary module mocks; no worker processes are started."""

from vericlue_ml.common.result import Module
from vericlue_ml.mock.detectors import MockDetector
from vericlue_ml.runtime.voice_wire import KINDS


class MockSessionVoiceDetector(MockDetector):
    def __init__(self, kind: str) -> None:
        super().__init__(Module(KINDS[kind]))
