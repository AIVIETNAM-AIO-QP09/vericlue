"""RAM lipsync mock never produces an authentication verdict."""

from vericlue_ml.common.result import ModuleResult


class MockRamLipSyncDetector:
    name = "lipsync"
    version = "mock-ram-lipsync@1"

    def predict(self, inp) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            model_version=self.version,
            status="degraded",
            gate="unclear",
            latency_ms=0,
        )
