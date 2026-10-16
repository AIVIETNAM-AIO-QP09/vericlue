"""Deterministic PLAT-08 regression: publish results only after advancing admission state."""

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import pytest

from vericlue_api.core.config import Settings
from vericlue_api.services import orchestrator as module
from vericlue_ml.common.result import ErrorCode, Module, ModuleResult, Status
from vericlue_ml.mock.detectors import MockDetector


@pytest.fixture
def publication_gate(monkeypatch):
    published, release = threading.Event(), threading.Event()
    original_job = module._Job
    created = []

    class GatedFuture(Future):
        def __init__(self):
            super().__init__()
            self.is_first = not created
            created.append(self)

        def set_result(self, result):
            super().set_result(result)
            if self.is_first:
                published.set()
                assert release.wait(timeout=3), "test must release result publisher"

    # Dataclass default_factory captures the original class at definition time;
    # inject through _Job's normal result parameter to use the patched Future.
    monkeypatch.setattr(module, "Future", GatedFuture)

    def job_factory(*args, **kwargs):
        return original_job(*args, result=module.Future(), **kwargs)

    monkeypatch.setattr(module, "_Job", job_factory)
    try:
        yield published, release
    finally:
        release.set()


class RecordingDetector:
    name, version = "quality", "synthetic@slot-release"

    def __init__(self, action=None):
        self.action = action
        self.order = []
        self.active = self.peak = 0
        self.lock = threading.Lock()

    def predict(self, inp):
        with self.lock:
            self.order.append(inp.session_id)
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.action:
                self.action(inp)
            return ModuleResult(
                module=Module.QUALITY,
                model_version=self.version,
                status=Status.OK,
                gate="pass",
                latency_ms=0,
            )
        finally:
            with self.lock:
                self.active -= 1


def configured(detector, queue_size, timeout=1):
    engine = module.Orchestrator(
        Settings(
            detector_workers=9, detector_queue_size=queue_size, detector_timeout_seconds=timeout
        ),
        detector_factory=lambda name: detector if name == Module.QUALITY else MockDetector(name),
    )
    engine.start()
    return engine


def invoke(engine, identifier):
    return engine.run([Module.QUALITY], session_id=identifier, scenario="genuine")[Module.QUALITY]


def pending(engine, count):
    limit = time.perf_counter() + 1
    while True:
        with engine._lifecycle:
            actual = len(engine._queues[Module.QUALITY])
        if actual == count:
            return
        assert time.perf_counter() < limit, f"expected {count} waiting jobs, observed {actual}"
        time.sleep(0.002)


@pytest.mark.parametrize("queue_size", [0, 3])
def test_completed_result_releases_slot_before_waiter_observes_success(
    publication_gate, queue_size
):
    published, release = publication_gate
    detector = RecordingDetector()
    engine = configured(detector, queue_size)
    try:
        first = invoke(engine, "first")
        assert first.status == Status.OK
        assert published.wait(timeout=1)
        # The first driver's set_result has returned success to the caller but remains paused.
        second = invoke(engine, "second")
        assert second.status == Status.OK and second.error_code is None
        assert detector.order == ["first", "second"]
        assert detector.peak == 1
    finally:
        release.set()
        engine.close()


def test_reserved_fifo_successor_keeps_order_while_predecessor_publisher_is_paused(
    publication_gate,
):
    published, release = publication_gate
    entered, finish_first = threading.Event(), threading.Event()

    def action(inp):
        if inp.session_id == "first":
            entered.set()
            assert finish_first.wait(timeout=3)

    detector = RecordingDetector(action)
    engine = configured(detector, queue_size=3)
    try:
        with ThreadPoolExecutor(max_workers=3) as workers:
            first = workers.submit(invoke, engine, "first")
            try:
                assert entered.wait(timeout=1)
                second = workers.submit(invoke, engine, "second")
                pending(engine, 1)
                finish_first.set()
                assert first.result(timeout=1).status == Status.OK
                assert published.wait(timeout=1)
                third = workers.submit(invoke, engine, "third")
                pending(engine, 1)
                assert detector.order == ["first"]
                release.set()
                assert second.result(timeout=1).status == Status.OK
                assert third.result(timeout=1).status == Status.OK
                assert detector.order == ["first", "second", "third"]
                assert detector.peak == 1
            finally:
                finish_first.set()
                release.set()
    finally:
        finish_first.set()
        release.set()
        engine.close()


def test_timed_out_inference_releases_slot_when_it_finishes_before_publishing(publication_gate):
    published, release = publication_gate
    entered, finish = threading.Event(), threading.Event()

    def action(inp):
        if inp.session_id == "expired":
            entered.set()
            assert finish.wait(timeout=3)

    detector = RecordingDetector(action)
    engine = configured(detector, queue_size=0, timeout=0.05)
    try:
        first = invoke(engine, "expired")
        assert entered.is_set()
        assert first.status == Status.ERROR and first.error_code == ErrorCode.E_TIMEOUT
        busy = invoke(engine, "still-running")
        assert busy.error_code == ErrorCode.E_TIMEOUT
        assert detector.order == ["expired"]
        finish.set()
        assert published.wait(timeout=1)
        fresh = invoke(engine, "fresh")
        assert fresh.status == Status.OK
        assert detector.order == ["expired", "fresh"] and detector.peak == 1
        assert first.status == Status.ERROR and first.error_code == ErrorCode.E_TIMEOUT
    finally:
        finish.set()
        release.set()
        engine.close()
