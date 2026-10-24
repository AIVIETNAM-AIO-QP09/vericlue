"""No model/device needed; timing mocks never claim content or authentication success."""

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult


class MockReadingTimingDetector:
    name = "voice_challenge"
    version = "mock-reading-timing@1"

    def predict(self, inp: DetectorInput) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status="degraded",
            gate="unclear",
            quality={"diagnostic_only": True},
            latency_ms=0,
        )
