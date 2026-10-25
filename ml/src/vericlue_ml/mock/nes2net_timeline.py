"""Raw-only mock; no pretend time coverage or authentication success."""

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult


class MockNes2NetTimelineDetector:
    name = "voice_spoof"
    version = "mock-nes2net-timeline@1"

    def predict(self, inp: DetectorInput) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status="degraded",
            gate="unclear",
            quality={"diagnostic_only": True, "aggregation": "none"},
            latency_ms=0,
        )
