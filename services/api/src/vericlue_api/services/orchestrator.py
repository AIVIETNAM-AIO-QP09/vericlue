"""Bounded parallel inference; workers never access request state or the database."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from copy import copy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, Thread
from time import perf_counter
from typing import Any, Literal

from vericlue_api.core.config import Settings
from vericlue_ml.common.detector import Detector, DetectorInput
from vericlue_ml.common.result import ErrorCode, Evidence, Module, ModuleResult, Status
from vericlue_ml.face.fsvfm import FsvfmPadDetector
from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.face.match import FaceMatchDetector
from vericlue_ml.face.pad import FacePadDetector
from vericlue_ml.face.quality import QualityDetector
from vericlue_ml.face.session_attack import SessionAttackDetector
from vericlue_ml.face.video_match import VideoFaceMatchDetector
from vericlue_ml.presence.chromapulse import ChromaPulseDetector
from vericlue_ml.presence.color_regions import ColorObservationReader
from vericlue_ml.presence.gaze import GazeDetector
from vericlue_ml.presence.head_turn import HeadTurnDetector
from vericlue_ml.presence.landmarks import FaceObservationReader
from vericlue_ml.registry import get_detector
from vericlue_ml.router.policy import TrustRouter
from vericlue_ml.voice.antispoof import AntiDeepfakeDetector
from vericlue_ml.voice.challenge import VoiceChallengeDetector
from vericlue_ml.voice.syncnet import SyncNetDetector

logger = logging.getLogger(__name__)


@dataclass
class _Job:
    module: Module
    inp: DetectorInput
    submitted: float
    deadline: float
    result: Future = field(default_factory=Future)


class Orchestrator:
    """One serialized detector instance per module, with bounded FIFO waiting queues."""

    def __init__(
        self, settings: Settings, *, detector_factory: Callable[[Module], Detector] | None = None
    ) -> None:
        self.settings = settings
        self.router = TrustRouter(settings.router_config, profile=settings.router_profile)
        self._factory = detector_factory or self._default_detector
        self._detectors: dict[Module, Detector] = {}
        self._failed: set[Module] = set()
        self._queues: dict[Module, deque[_Job]] = {module: deque() for module in Module}
        self._running: set[Module] = set()
        self._lifecycle = Lock()
        self._started = self._closed = False
        self._executor: ThreadPoolExecutor | None = None
        self._face_reader = FaceObservationReader()

    def _default_detector(self, module: Module) -> Detector:
        if module == Module.FACE_MATCH and self.settings.identity_lab_url:
            # Identity opt-in is deliberately hybrid: OCR and face matching are real,
            # even when the remaining API detectors are mocked for the demo.
            artifact = self.settings.identity_face_calibration
            if self.settings.identity_face_from_video:
                return VideoFaceMatchDetector(
                    reader=self._face_reader,
                    calibration_path=Path(artifact) if artifact else None,
                    with_consistency=self.settings.identity_consistency_required,
                    consistency_path=Path(self.settings.identity_consistency_calibration)
                    if self.settings.identity_consistency_calibration
                    else None,
                )
            return FaceMatchDetector(calibration_path=Path(artifact) if artifact else None)
        if self.settings.session_face_checks:
            if module == Module.GAZE_TRACKING:
                return GazeDetector(self._face_reader)
            if module == Module.HEAD_TURN:
                return HeadTurnDetector(self._face_reader)
        if self.settings.session_face_models:
            if module == Module.FACE_PAD:
                return SessionAttackDetector(FsvfmPadDetector(), self._face_reader)
            if module == Module.FACE_DEEPFAKE:
                return SessionAttackDetector(FaceDeepfakeDetector(), self._face_reader)
            if module == Module.CHROMAPULSE:
                return ChromaPulseDetector(ColorObservationReader(self._face_reader))
        return get_detector(module, mock=self.settings.use_mock_models)

    def loaded_detector(self, module: Module) -> Detector | None:
        """Bộ phát hiện đã preload (dùng lại cho giám định, tránh nạp mô hình hai lần); None nếu chưa có."""
        with self._lifecycle:
            return self._detectors.get(module)

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
            modules = list(self.router.profile.modules)
            if self.settings.identity_lab_url:
                modules.append(Module.FACE_MATCH)
            if self.settings.session_face_checks:
                modules.extend((Module.GAZE_TRACKING, Module.HEAD_TURN))
            for module in dict.fromkeys(modules):
                try:
                    detector = self._factory(module)
                    if Module(detector.name) != module:
                        raise ValueError("Detector module mismatch")
                    if isinstance(detector, VoiceChallengeDetector):
                        # Registry caches the model; each application owns its policy wrapper.
                        detector = copy(detector)
                        detector.match_config = self.settings.router_config.voice
                    preload = getattr(detector, "preload", None)
                    if isinstance(detector, SyncNetDetector):
                        # Advisory lipsync must not occupy the main models' GPU at startup.
                        detector.configure(
                            models_dir=Path(self.settings.models_dir),
                            device=self.settings.lipsync_device,
                        )
                    elif isinstance(
                        detector, (GazeDetector, HeadTurnDetector, ChromaPulseDetector)
                    ):
                        preload(models_dir=Path(self.settings.models_dir))
                    elif preload is not None:
                        if isinstance(
                            detector,
                            (
                                VoiceChallengeDetector,
                                AntiDeepfakeDetector,
                                FacePadDetector,
                                FaceDeepfakeDetector,
                                QualityDetector,
                                FaceMatchDetector,
                                SessionAttackDetector,
                            ),
                        ):
                            preload(
                                models_dir=Path(self.settings.models_dir),
                                device=self.settings.device,
                            )
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
            if self._closed:
                return
            self._closed = True
            for queue in self._queues.values():
                while queue:
                    job = queue.popleft()
                    finished = perf_counter()
                    job.result.set_result(
                        (
                            self._error(
                                job.module,
                                ErrorCode.E_TIMEOUT,
                                (finished - job.submitted) * 1000,
                                reason="timeout",
                            ),
                            finished,
                        )
                    )
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=True)
                if (
                    self.settings.identity_face_from_video
                    or self.settings.session_face_checks
                    or self.settings.session_face_models
                ):
                    executor, reader = self._executor, self._face_reader

                    def release_reader() -> None:
                        # Wait outside the request/shutdown path; no task may reopen the
                        # shared reader between close and its last native inference.
                        executor.shutdown(wait=True)
                        reader.close()

                    Thread(target=release_reader, name="vericlue-face-cleanup", daemon=True).start()

    def _error(
        self, module: Module, code: ErrorCode, latency_ms: float, *, reason: str | None = None
    ) -> ModuleResult:
        detector = self._detectors.get(module)
        return ModuleResult(
            module=module,
            model_version=getattr(detector, "version", "unavailable"),
            status=Status.ERROR,
            error_code=code,
            latency_ms=max(0.0, latency_ms),
            evidence=[
                Evidence(
                    type="text",
                    name="orchestration_reason",
                    value=reason,
                    label_vi="Bước này đang tắt ở chế độ MVP"
                    if reason == "disabled_by_profile"
                    else None,
                )
            ]
            if reason
            else [],
        )

    def _predict(
        self, module: Module, inp: DetectorInput, submitted: float, deadline: float
    ) -> tuple[ModuleResult, float]:
        if perf_counter() >= deadline:
            finished = perf_counter()
            return self._error(
                module, ErrorCode.E_TIMEOUT, (finished - submitted) * 1000, reason="timeout"
            ), finished
        try:
            result = self._detectors[module].predict(inp)
            if not isinstance(result, ModuleResult) or Module(result.module) != module:
                raise ValueError("Invalid detector result")
            result = ModuleResult.model_validate(result.model_dump())
        except Exception:
            result = self._error(module, ErrorCode.E_INTERNAL, 0.0)
        finished = perf_counter()
        return result.model_copy(update={"latency_ms": (finished - submitted) * 1000}), finished

    def _drain(self, job: _Job) -> None:
        # Only one executor worker per module; queued requests do not occupy pool threads.
        module = job.module
        while True:
            result = self._predict(module, job.inp, job.submitted, job.deadline)
            with self._lifecycle:
                queue = self._queues[module]
                next_job = queue.popleft() if queue else None
                if next_job is None:
                    self._running.remove(module)
            # Admission must observe the released/reserved slot before callers see success.
            # Publish outside the lifecycle lock so callbacks cannot block admission.
            job.result.set_result(result)
            if next_job is None:
                return
            job = next_job

    def _prune(self, module: Module) -> None:
        # Waiting jobs are owned by this queue, so expiring them creates no executor tombstones.
        now = perf_counter()
        queue = self._queues[module]
        remaining = deque()
        while queue:
            job = queue.popleft()
            if job.deadline <= now:
                job.result.set_result(
                    (
                        self._error(
                            module,
                            ErrorCode.E_TIMEOUT,
                            (now - job.submitted) * 1000,
                            reason="timeout",
                        ),
                        now,
                    )
                )
            else:
                remaining.append(job)
        self._queues[module] = remaining

    def run(
        self,
        modules: Iterable[Module],
        *,
        session_id: str | None,
        scenario: str,
        images: list[Path] | None = None,
        reference_image: Path | None = None,
        image_roles: list[Literal["front", "left", "right"]] | None = None,
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
            reference_image=reference_image,
            image_roles=image_roles or [],
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
                if module not in self.router.profile.modules and not (
                    module == Module.FACE_MATCH
                    and self.settings.identity_lab_url
                    or module in {Module.GAZE_TRACKING, Module.HEAD_TURN}
                    and self.settings.session_face_checks
                ):
                    out[module] = self._error(
                        module,
                        ErrorCode.E_INTERNAL,
                        (perf_counter() - started) * 1000,
                        reason="disabled_by_profile",
                    )
                    continue
                if not self._started or self._closed or module in self._failed:
                    out[module] = self._error(
                        module, ErrorCode.E_INTERNAL, (perf_counter() - started) * 1000
                    )
                    continue
                if perf_counter() >= deadline:
                    out[module] = self._error(
                        module,
                        ErrorCode.E_TIMEOUT,
                        (perf_counter() - started) * 1000,
                        reason="timeout",
                    )
                    continue
                self._prune(module)
                if (
                    module in self._running
                    and len(self._queues[module]) >= self.settings.detector_queue_size
                ):
                    out[module] = self._error(
                        module,
                        ErrorCode.E_TIMEOUT,
                        (perf_counter() - started) * 1000,
                        reason="busy",
                    )
                    continue
                job = _Job(module, inp.model_copy(deep=True), started, deadline)
                futures[module] = job.result
                if module in self._running:
                    self._queues[module].append(job)
                else:
                    self._running.add(module)
                    try:
                        self._executor.submit(self._drain, job)
                    except Exception:
                        self._running.remove(module)
                        job.result.set_result(
                            (
                                self._error(
                                    module, ErrorCode.E_INTERNAL, (perf_counter() - started) * 1000
                                ),
                                perf_counter(),
                            )
                        )
        if futures:
            wait(futures.values(), timeout=max(0.0, deadline - perf_counter()))
        for module, future in futures.items():
            if future.done() and not future.cancelled():
                result, finished = future.result()
                if finished <= deadline:
                    out[module] = result
                    continue
            # The driver owns pending/running jobs; never enqueue unbounded executor work.
            # Discard late results; waiting jobs are pruned before further admission.
            out[module] = self._error(
                module, ErrorCode.E_TIMEOUT, (perf_counter() - started) * 1000, reason="timeout"
            )
        for module, result in out.items():
            reason = next(
                (e.value for e in result.evidence if e.name == "orchestration_reason"), None
            )
            logger.info(
                "detector_result session_id=%s module=%s model_version=%s status=%s error_code=%s reason=%s latency_ms=%.3f",
                session_id,
                module,
                result.model_version,
                result.status,
                result.error_code,
                reason,
                result.latency_ms,
            )
        return out
