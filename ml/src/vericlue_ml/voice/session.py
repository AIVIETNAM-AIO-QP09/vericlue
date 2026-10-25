"""Session adapters; Qwen content, forced timing, NES2Net and lipsync stay distinct."""

from time import monotonic

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Evidence, ModuleResult
from vericlue_ml.router.config import VoiceConfig
from vericlue_ml.runtime.voice_client import VoiceWorkerClient
from vericlue_ml.runtime.voice_wire import KINDS, expected_version, source_hashes


class SessionVoiceDetector:
    """One API ModuleResult, using a private compatible runtime and one server-owned audio."""

    def __init__(
        self, client: VoiceWorkerClient, kind: str, *, match_config: VoiceConfig | None = None
    ) -> None:
        self.client, self.kind = client, kind
        self.name, self.version = KINDS[kind], expected_version(kind)
        self.match_config = match_config

    def preload(self) -> None:
        self.client.preload()

    def predict(self, inp: DetectorInput) -> ModuleResult:
        started = monotonic()
        if self.kind != "content":
            return self.client.predict(self.kind, inp)
        sources = None
        try:
            sources = source_hashes(inp, self.client.media_root, "content")
            if self.match_config is not None:
                inp = inp.model_copy(
                    update={
                        "metadata": {
                            **inp.metadata,
                            "voice_match_config": self.match_config.model_dump(mode="json"),
                        }
                    }
                )
            result = self.client.predict("content", inp)
            timing = self.client.predict(
                "timing", inp, timeout=max(0.001, self.client.timeout - (monotonic() - started))
            )
            if source_hashes(inp, self.client.media_root, "content") != sources:
                raise ValueError("Audio changed between content and timing")
            result.quality["reading_timing_status"] = timing.status
            result.evidence.append(
                Evidence(type="scalar", name="reading_timing_result", value=timing.to_contract())
            )
            return result
        except Exception:
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status="error",
                gate="unclear",
                error_code="E_INTEGRITY" if sources is not None else "E_DECODE",
                latency_ms=(monotonic() - started) * 1000,
            )
