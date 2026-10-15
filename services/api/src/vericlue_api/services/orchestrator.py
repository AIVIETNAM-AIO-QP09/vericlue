"""Bounded parallel inference; workers never access request state or the database."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any

from vericlue_api.core.config import Settings
from vericlue_ml.common.detector import Detector, DetectorInput
from vericlue_ml.common.result import ErrorCode, Module, ModuleResult, Status
from vericlue_ml.registry import get_detector
from vericlue_ml.voice.challenge import VoiceChallengeDetector

logger = logging.getLogger(__name__)


class Orchestrator:
    """One detector instance and at most one outstanding task per module/process."""

    def __init__(
        self, settings: Settings, *, detector_factory: Callable[[Module], Detector] | None = None
    ) -> None:
        self.settings = settings
        self._factory = detector_factory or (
            lambda module: get_detector(module, mock=settings.use_mock_models)
        )
        self._detectors: dict[Module, Detector] = {}
        self._failed: set[Module] = set()
        self._slots = {module: Lock() for module in Module}
        self._lifecycle = Lock()
        self._started = self._closed = False
        self._executor: ThreadPoolExecutor | None = None

    @property
    def failed_modules(self) -> list[str]:
        """Only public module names; never expose preload exception details."""
        with self._lifecycle:
            return sorted(str(module) for module in self._failed)

    def start(self) -> None:
        """Resolve/preload once; failed modules remain unavailable until restart."""
        with self._lifecycle:
            if self._closed:
                raise RuntimeError("Orchestrator is closed")
            if self._started:
                return
            for module in Module:
                try:
                    detector = self._factory(module)
                    if Module(detector.name) != module:
                        raise ValueError("Detector module mismatch")
                    preload = getattr(detector, "preload", None)
                    if preload is not None:
                        if isinstance(detector, VoiceChallengeDetector):
                            preload(models_dir=Path(self.settings.models_dir))
                        else:
                            preload()
                    self._detectors[module] = detector
                except Exception:
                    self._failed.add(module)
                    logger.warning("detector_preload_failed module=%s", module)
            self._executor = ThreadPoolExecutor(
                max_workers=self.settings.detector_workers, thread_name_prefix="vericlue-detector"
            )
            self._started = True

    def close(self) -> None:
        """Stop accepting work; running inference cannot be safely killed in a thread."""
        with self._lifecycle:
            self._closed = True
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=True)

    def _error(self, module: Module, code: ErrorCode, latency_ms: float) -> ModuleResult:
        detector = self._detectors.get(module)
        return ModuleResult(
            module=module,
            model_version=getattr(detector, "version", "unavailable"),
            status=Status.ERROR,
            error_code=code,
            latency_ms=max(0.0, latency_ms),
        )

    def _predict(
        self, module: Module, inp: DetectorInput, submitted: float, deadline: float
    ) -> tuple[ModuleResult, float]:
        if perf_counter() >= deadline:
            finished = perf_counter()
            return self._error(module, ErrorCode.E_TIMEOUT, (finished - submitted) * 1000), finished
        try:
            result = self._detectors[module].predict(inp)
            if not isinstance(result, ModuleResult) or Module(result.module) != module:
                raise ValueError("Invalid detector result")
            result = ModuleResult.model_validate(result.model_dump())
        except Exception:
            result = self._error(module, ErrorCode.E_INTERNAL, 0.0)
        finished = perf_counter()
        return result.model_copy(update={"latency_ms": (finished - submitted) * 1000}), finished

    def run(
        self,
        modules: Iterable[Module],
        *,
        session_id: str | None,
        scenario: str,
        images: list[Path] | None = None,
        video: Path | None = None,
        audio: Path | None = None,
        signals: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
        deadline: float | None = None,
    ) -> dict[Module, ModuleResult]:
        """Use a common submission deadline; discard late results without state writes."""
        started = perf_counter()
        deadline = min(
            started + self.settings.detector_timeout_seconds,
            deadline if deadline is not None else float("inf"),
        )
        inp = DetectorInput(
            session_id=session_id,
            images=images or [],
            video=video,
            audio=audio,
            signals=signals or {},
            metadata={"scenario": scenario, **(extra_metadata or {})},
        )
        out: dict[Module, ModuleResult] = {}
        futures: dict[Module, Future] = {}
        with self._lifecycle:
            for value in dict.fromkeys(modules):
                module = Module(value)
                if not self._started or self._closed or module in self._failed:
                    out[module] = self._error(
                        module, ErrorCode.E_INTERNAL, (perf_counter() - started) * 1000
                    )
                    continue
                if perf_counter() >= deadline:
                    out[module] = self._error(
                        module, ErrorCode.E_TIMEOUT, (perf_counter() - started) * 1000
                    )
                    continue
                slot = self._slots[module]
                if not slot.acquire(blocking=False):
                    out[module] = self._error(
                        module, ErrorCode.E_TIMEOUT, (perf_counter() - started) * 1000
                    )
                    continue
                try:
                    future = self._executor.submit(
                        self._predict, module, inp.model_copy(deep=True), started, deadline
                    )
                    future.add_done_callback(lambda _future, slot=slot: slot.release())
                    futures[module] = future
                except Exception:
                    slot.release()
                    out[module] = self._error(
                        module, ErrorCode.E_INTERNAL, (perf_counter() - started) * 1000
                    )
        if futures:
            wait(futures.values(), timeout=max(0.0, deadline - perf_counter()))
        for module, future in futures.items():
            if future.done() and not future.cancelled():
                result, finished = future.result()
                if finished <= deadline:
                    out[module] = result
                    continue
            # Keep the slot until queued/running work really finishes; cancelling a queued
            # Future would release it while a tombstone remains in the executor queue.
            out[module] = self._error(
                module, ErrorCode.E_TIMEOUT, (perf_counter() - started) * 1000
            )
        for module, result in out.items():
            logger.info(
                "detector_result session_id=%s module=%s model_version=%s status=%s error_code=%s latency_ms=%.3f",
                session_id,
                module,
                result.model_version,
                result.status,
                result.error_code,
                result.latency_ms,
            )
        return out
