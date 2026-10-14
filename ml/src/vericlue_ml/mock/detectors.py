"""Bộ phát hiện giả lập: một bộ cho mỗi `Module`, trả kết quả theo kịch bản.

Chọn kịch bản qua `DetectorInput.metadata["scenario"]` (mặc định "genuine").
"""

from __future__ import annotations

import copy

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module, ModuleResult
from vericlue_ml.mock.scenarios import spec_for

MOCK_VERSION = "mock@0.1"
_MOCK_LATENCY_MS = 5.0


class MockDetector:
    """Bộ phát hiện giả lập cho một module."""

    def __init__(self, module: Module) -> None:
        self.module = Module(module)
        self.name = self.module.value
        self.version = MOCK_VERSION

    def predict(self, inp: DetectorInput) -> ModuleResult:
        scenario = str(inp.metadata.get("scenario", "genuine"))
        spec = copy.deepcopy(spec_for(self.module, scenario))
        return ModuleResult(
            module=self.module,
            model_version=self.version,
            latency_ms=_MOCK_LATENCY_MS,
            **spec,
        )

    def __repr__(self) -> str:
        return f"MockDetector({self.module.value})"


MOCK_DETECTORS: dict[Module, MockDetector] = {m: MockDetector(m) for m in Module}
