"""PLAT-08 bounded parallel detector execution with CPU-only fakes."""

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.db.models import ModuleResultRow
from vericlue_api.main import create_app
from vericlue_api.services import orchestrator as orchestration
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_ml.common.result import ErrorCode, Module, ModuleResult, Status
from vericlue_ml.mock.detectors import MockDetector


class FakeDetector:
    def __init__(self, module, action=None, preload_error=None):
        self.module = Module(module)
        self.name, self.version = self.module.value, "synthetic@1"
        self.action = action
        self.preload_error = preload_error
        self.preloads = 0
        self.calls = 0

    def preload(self):
        self.preloads += 1
        if self.preload_error:
            raise self.preload_error

    def predict(self, inp):
        self.calls += 1
        if self.action:
            return self.action(inp)
        return answer(self.module)


def answer(module, **changes):
    return ModuleResult(
        module=module, model_version="synthetic@1", status=Status.OK, latency_ms=0, **changes
    )


def run(orchestrator, modules, **changes):
    return orchestrator.run(modules, session_id="ses_synthetic", scenario="genuine", **changes)


def build(detectors=None, *, timeout=0.1):
    detectors = detectors or {}
    instances = {module: detectors.get(module, FakeDetector(module)) for module in Module}
    constructed = Counter()

    def factory(module):
        constructed[Module(module)] += 1
        return instances[Module(module)]

    orchestrator = Orchestrator(
        Settings(detector_timeout_seconds=timeout, detector_workers=9, detector_queue_size=0),
        detector_factory=factory,
    )
    return orchestrator, instances, constructed


def test_start_preloads_one_instance_once_and_runs_never_reload():
    orchestrator, instances, constructed = build()
    try:
        orchestrator.start()
        orchestrator.start()
        for _ in range(2):
            assert run(orchestrator, [Module.QUALITY])[Module.QUALITY].status == Status.OK
        assert all(count == 1 for count in constructed.values())
        assert set(constructed) == set(Module) - {Module.GAZE_TRACKING}
        assert all(
            instance.preloads == int(module != Module.GAZE_TRACKING)
            for module, instance in instances.items()
        )
        assert not orchestrator.failed_modules
    finally:
        orchestrator.close()


def test_prediction_functions_start_in_parallel():
    barrier = threading.Barrier(3)

    def predict(module):
        def action(_inp):
            barrier.wait(timeout=2)
            return answer(module)

        return action

    orchestrator, _, _ = build(
        {
            module: FakeDetector(module, predict(module))
            for module in (Module.QUALITY, Module.FACE_PAD)
        },
        timeout=1,
    )
    orchestrator.start()
    try:
        with ThreadPoolExecutor(max_workers=1) as worker:
            result = worker.submit(run, orchestrator, [Module.QUALITY, Module.FACE_PAD])
            barrier.wait(timeout=2)
            assert all(item.status == Status.OK for item in result.result(timeout=2).values())
    finally:
        orchestrator.close()


def test_timeout_uses_one_shared_deadline_and_late_results_never_replace_errors():
    release = threading.Event()
    started = {module: threading.Event() for module in list(Module)[:4]}

    def predict(module):
        def action(_inp):
            started[module].set()
            assert release.wait(timeout=3)
            return answer(module)

        return action

    orchestrator, _, _ = build(
        {module: FakeDetector(module, predict(module)) for module in started}, timeout=0.05
    )
    orchestrator.start()
    try:
        before = time.perf_counter()
        results = run(orchestrator, list(started))
        elapsed = time.perf_counter() - before
        assert elapsed < 0.17, "timeout must not be applied sequentially to every future"
        assert all(event.is_set() for event in started.values())
        assert all(
            item.status == Status.ERROR and item.error_code == ErrorCode.E_TIMEOUT
            for item in results.values()
        )
        release.set()
        orchestrator.close()
        assert all(
            item.status == Status.ERROR and item.error_code == ErrorCode.E_TIMEOUT
            for item in results.values()
        )
    finally:
        release.set()
        orchestrator.close()


def test_busy_module_is_not_queued_or_run_twice():
    entered, release = threading.Event(), threading.Event()

    def action(_inp):
        entered.set()
        assert release.wait(timeout=3)
        return answer(Module.FACE_PAD)

    detector = FakeDetector(Module.FACE_PAD, action)
    orchestrator, _, _ = build({Module.FACE_PAD: detector}, timeout=0.04)
    orchestrator.start()
    try:
        first = run(orchestrator, [Module.FACE_PAD])
        assert entered.is_set()
        assert first[Module.FACE_PAD].error_code == ErrorCode.E_TIMEOUT
        assert any(
            item.name == "orchestration_reason" and item.value == "timeout"
            for item in first[Module.FACE_PAD].evidence
        )
        second = run(orchestrator, [Module.FACE_PAD])
        assert second[Module.FACE_PAD].status == Status.ERROR
        assert second[Module.FACE_PAD].error_code == ErrorCode.E_TIMEOUT
        assert any(
            item.name == "orchestration_reason" and item.value == "busy"
            for item in second[Module.FACE_PAD].evidence
        )
        assert detector.calls == 1
    finally:
        release.set()
        orchestrator.close()


def test_preload_error_is_sticky_until_restart_and_reports_failed_module():
    detector = FakeDetector(Module.FACE_PAD, preload_error=RuntimeError("synthetic missing model"))
    orchestrator, _, constructed = build({Module.FACE_PAD: detector})
    try:
        orchestrator.start()
        assert Module.FACE_PAD.value in orchestrator.failed_modules
        detector.preload_error = None
        for _ in range(2):
            result = run(orchestrator, [Module.FACE_PAD])[Module.FACE_PAD]
            assert result.status == Status.ERROR
            assert result.error_code == ErrorCode.E_INTERNAL
        assert detector.calls == 0 and detector.preloads == 1
        assert constructed[Module.FACE_PAD] == 1
    finally:
        orchestrator.close()


@pytest.mark.parametrize("failure", ["exception", "wrong_module", "invalid_result"])
def test_predict_failure_never_becomes_accepted(failure):
    def action(_inp):
        if failure == "exception":
            raise RuntimeError("private recognized_text expected_text")
        if failure == "wrong_module":
            return answer(Module.QUALITY)
        return {"status": "ok", "prob_attack": 0}

    orchestrator, _, _ = build({Module.FACE_PAD: FakeDetector(Module.FACE_PAD, action)})
    orchestrator.start()
    try:
        result = run(orchestrator, [Module.FACE_PAD])[Module.FACE_PAD]
        assert result.module == Module.FACE_PAD
        assert result.status == Status.ERROR and result.error_code == ErrorCode.E_INTERNAL
        assert result.prob_attack is None
    finally:
        orchestrator.close()


def test_degraded_status_is_preserved_as_unusable():
    detector = FakeDetector(
        Module.FACE_PAD,
        lambda _: ModuleResult(
            module=Module.FACE_PAD,
            model_version="synthetic@1",
            status=Status.DEGRADED,
            error_code=ErrorCode.E_LOW_QUALITY,
            latency_ms=0,
        ),
    )
    orchestrator, _, _ = build({Module.FACE_PAD: detector})
    orchestrator.start()
    try:
        result = run(orchestrator, [Module.FACE_PAD])[Module.FACE_PAD]
        assert result.status == Status.DEGRADED and not result.is_usable
    finally:
        orchestrator.close()


def test_detector_input_nested_values_are_isolated_from_other_workers_and_caller():
    mutated = threading.Event()
    observed = []

    def mutate(inp):
        inp.signals["nested"]["values"].append("changed")
        inp.metadata["nested"]["values"].append("changed")
        inp.images.append(Path("changed.jpg"))
        mutated.set()
        return answer(Module.QUALITY)

    def inspect_input(inp):
        assert mutated.wait(timeout=2)
        observed.append((inp.signals, inp.metadata["nested"], inp.images))
        return answer(Module.FACE_PAD)

    orchestrator, _, _ = build(
        {
            Module.QUALITY: FakeDetector(Module.QUALITY, mutate),
            Module.FACE_PAD: FakeDetector(Module.FACE_PAD, inspect_input),
        },
        timeout=1,
    )
    orchestrator.start()
    signals, metadata, images = (
        {"nested": {"values": []}},
        {"nested": {"values": []}},
        [Path("original.jpg")],
    )
    try:
        results = run(
            orchestrator,
            [Module.QUALITY, Module.FACE_PAD],
            signals=signals,
            extra_metadata=metadata,
            images=images,
        )
        assert all(item.status == Status.OK for item in results.values())
        assert observed == [({"nested": {"values": []}}, {"values": []}, [Path("original.jpg")])]
        assert signals == {"nested": {"values": []}}
        assert metadata == {"nested": {"values": []}} and images == [Path("original.jpg")]
    finally:
        orchestrator.close()


def test_timing_logs_do_not_include_transcripts_or_raw_exception(caplog):
    def action(_inp):
        raise RuntimeError("SECRET_TRANSCRIPT expected_text recognized_text")

    orchestrator, _, _ = build({Module.FACE_PAD: FakeDetector(Module.FACE_PAD, action)})
    orchestrator.start()
    try:
        with caplog.at_level("INFO"):
            results = run(
                orchestrator, [Module.FACE_PAD], extra_metadata={"prompt": "SECRET_PROMPT"}
            )
        assert results[Module.FACE_PAD].latency_ms >= 0
        assert caplog.records
        assert "ses_synthetic" in caplog.text and "face_pad" in caplog.text
        assert "SECRET_TRANSCRIPT" not in caplog.text and "SECRET_PROMPT" not in caplog.text
        assert "recognized_text" not in caplog.text and "expected_text" not in caplog.text
    finally:
        orchestrator.close()


def test_health_preload_failure_is_degraded_sticky_and_names_only(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    get_settings.cache_clear()
    constructed = Counter()
    failed = FakeDetector(Module.FACE_PAD, preload_error=RuntimeError("SECRET_MODEL_PATH"))

    def factory(module, *, mock=None):
        constructed[Module(module)] += 1
        return (
            failed
            if Module(module) == Module.FACE_PAD
            else FakeDetector(module, MockDetector(module).predict)
        )

    monkeypatch.setattr(orchestration, "get_detector", factory)
    with TestClient(create_app()) as client:
        first = client.get("/healthz")
        assert first.status_code == 200
        assert first.json()["status"] == "degraded"
        assert first.json()["failed_modules"] == ["face_pad"]
        assert "SECRET_MODEL_PATH" not in first.text
        failed.preload_error = None
        assert client.get("/healthz").json()["failed_modules"] == ["face_pad"]
        created = client.post("/v1/sessions").json()
        finalized = client.post(
            f"/v1/sessions/{created['session_id']}/finalize",
            headers={"Authorization": "Bearer " + created["token"]},
        )
        assert finalized.json()["status"] == "review"
        assert all(value == 1 for value in constructed.values())
        assert failed.calls == 0
    get_settings.cache_clear()


def test_api_lifespan_preloads_each_detector_once_per_application(monkeypatch):
    all_instances = []

    def factory(module, *, mock=None):
        instance = FakeDetector(module)
        all_instances.append(instance)
        return instance

    monkeypatch.setattr(orchestration, "get_detector", factory)
    for _ in range(2):
        with TestClient(create_app()) as client:
            assert client.get("/healthz").json()["failed_modules"] == []
            client.get("/healthz")
            client.post("/v1/sessions")
    assert len(all_instances) == (len(Module) - 1) * 2
    assert all(instance.preloads == 1 for instance in all_instances)


def test_voice_response_keeps_recognized_expected_text_and_scores_internal(monkeypatch):
    def challenge(_inp):
        return answer(
            Module.VOICE_CHALLENGE,
            gate="pass",
            score=0.1,
            evidence=[
                {"type": "text", "name": "recognized_text", "value": "SECRET_RECOGNIZED"},
                {"type": "text", "name": "expected_text", "value": "SECRET_EXPECTED"},
            ],
        )

    def factory(module, *, mock=None):
        return (
            FakeDetector(module, challenge)
            if Module(module) == Module.VOICE_CHALLENGE
            else MockDetector(module)
        )

    monkeypatch.setattr(orchestration, "get_detector", factory)
    with TestClient(create_app()) as client:
        created = client.post("/v1/sessions", headers={"X-Mock-Scenario": "voice_clone"}).json()
        sid = created["session_id"]
        headers = {"Authorization": "Bearer " + created["token"]}
        finalized = client.post(f"/v1/sessions/{sid}/finalize", headers=headers)
        assert finalized.json()["status"] == "voice_challenge"
        response = client.post(
            f"/v1/sessions/{sid}/voice",
            headers=headers,
            files={"audio": ("voice.wav", b"synthetic audio", "audio/wav")},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "review"}
        for forbidden in (
            "recognized_text",
            "expected_text",
            "SECRET_RECOGNIZED",
            "SECRET_EXPECTED",
            '"score"',
            '"prob_attack"',
            '"evidence"',
            '"modules"',
        ):
            assert forbidden not in response.text
        with client.app.state.vericlue.transaction() as state:
            result = state.sessions.get(sid).results[Module.VOICE_CHALLENGE]
            assert result.score == 0.1
            assert {evidence.name for evidence in result.evidence} == {
                "recognized_text",
                "expected_text",
            }


def test_default_four_second_detector_timeout_keeps_finalize_under_five_seconds(monkeypatch):
    monkeypatch.delenv("DETECTOR_TIMEOUT_SECONDS", raising=False)
    get_settings.cache_clear()
    entered, release = threading.Event(), threading.Event()

    def blocked_face(_inp):
        if (_inp.session_id or "").startswith("ses_demo_"):
            return MockDetector(Module.FACE_PAD).predict(_inp)
        entered.set()
        assert release.wait(timeout=10)
        return answer(Module.FACE_PAD, prob_attack=0)

    def factory(module, *, mock=None):
        return (
            FakeDetector(module, blocked_face)
            if Module(module) == Module.FACE_PAD
            else MockDetector(module)
        )

    monkeypatch.setattr(orchestration, "get_detector", factory)
    try:
        with TestClient(create_app()) as client:
            assert client.app.state.vericlue.settings.detector_timeout_seconds == 4
            created = client.post("/v1/sessions").json()
            sid = created["session_id"]
            started = time.perf_counter()
            response = client.post(
                f"/v1/sessions/{sid}/finalize",
                headers={"Authorization": "Bearer " + created["token"]},
            )
            elapsed = time.perf_counter() - started
            assert entered.is_set()
            assert response.status_code == 200 and response.json() == {"status": "review"}
            assert 3.5 <= elapsed <= 5, f"whole finalize endpoint took {elapsed:.3f}s"
            with client.app.state.vericlue.transaction() as state:
                result = state.sessions.get(sid).results[Module.FACE_PAD]
                assert result.status == Status.ERROR and result.error_code == ErrorCode.E_TIMEOUT
            release.set()
    finally:
        release.set()
        get_settings.cache_clear()


@pytest.mark.parametrize("status", [Status.ERROR, Status.DEGRADED])
def test_required_detector_error_or_degraded_never_passes_finalize(monkeypatch, status):
    def failed_face(_inp):
        return ModuleResult(
            module=Module.FACE_PAD,
            model_version="synthetic@1",
            status=status,
            error_code=ErrorCode.E_INTERNAL,
            latency_ms=0,
        )

    def factory(module, *, mock=None):
        return (
            FakeDetector(module, failed_face)
            if Module(module) == Module.FACE_PAD
            else MockDetector(module)
        )

    monkeypatch.setattr(orchestration, "get_detector", factory)
    with TestClient(create_app()) as client:
        created = client.post("/v1/sessions").json()
        response = client.post(
            f"/v1/sessions/{created['session_id']}/finalize",
            headers={"Authorization": "Bearer " + created["token"]},
        )
        assert response.status_code == 200 and response.json() == {"status": "review"}


def test_expired_queued_work_keeps_slot_until_drained_without_predicting():
    release, entered = threading.Event(), threading.Event()

    def block_worker(_inp):
        entered.set()
        assert release.wait(timeout=3)
        return answer(Module.FACE_PAD)

    first = FakeDetector(Module.FACE_PAD, block_worker)
    queued = FakeDetector(Module.FACE_DEEPFAKE)
    instances = {module: FakeDetector(module) for module in Module}
    instances.update({Module.FACE_PAD: first, Module.FACE_DEEPFAKE: queued})
    orchestrator = Orchestrator(
        Settings(detector_timeout_seconds=0.04, detector_workers=1, detector_queue_size=0),
        detector_factory=lambda module: instances[Module(module)],
    )
    orchestrator.start()
    try:
        results = run(orchestrator, [Module.FACE_PAD, Module.FACE_DEEPFAKE])
        assert entered.is_set()
        assert all(result.error_code == ErrorCode.E_TIMEOUT for result in results.values())
        assert queued.calls == 0
        for _ in range(3):
            result = run(orchestrator, [Module.FACE_DEEPFAKE])[Module.FACE_DEEPFAKE]
            assert result.status == Status.ERROR and result.error_code == ErrorCode.E_TIMEOUT
        assert queued.calls == 0, (
            "expired queued work must retain its slot until the pool drains it"
        )
        release.set()
        deadline = time.perf_counter() + 2
        while True:
            fresh = run(orchestrator, [Module.FACE_DEEPFAKE])[Module.FACE_DEEPFAKE]
            if fresh.status == Status.OK:
                break
            assert fresh.error_code == ErrorCode.E_TIMEOUT
            assert time.perf_counter() < deadline, (
                "module slot was not released after queue drained"
            )
            time.sleep(0.005)
        assert queued.calls == 1, (
            "only the new request may invoke the detector, never the expired item"
        )
    finally:
        release.set()
        orchestrator.close()


def test_already_expired_absolute_deadline_never_invokes_detector():
    orchestrator, instances, _ = build()
    orchestrator.start()
    try:
        results = run(orchestrator, [Module.FACE_PAD], deadline=time.perf_counter() - 1)
        assert results[Module.FACE_PAD].error_code == ErrorCode.E_TIMEOUT
        assert instances[Module.FACE_PAD].calls == 0
    finally:
        orchestrator.close()


def test_absolute_deadline_limits_remaining_budget_after_prior_work():
    entered, release = threading.Event(), threading.Event()

    def blocked(_inp):
        entered.set()
        assert release.wait(timeout=3)
        return answer(Module.FACE_PAD)

    orchestrator, _, _ = build({Module.FACE_PAD: FakeDetector(Module.FACE_PAD, blocked)}, timeout=1)
    orchestrator.start()
    try:
        before = time.perf_counter()
        results = run(orchestrator, [Module.FACE_PAD], deadline=before + 0.04)
        assert time.perf_counter() - before < 0.2
        assert entered.is_set()
        assert results[Module.FACE_PAD].status == Status.ERROR
        assert results[Module.FACE_PAD].error_code == ErrorCode.E_TIMEOUT
    finally:
        release.set()
        orchestrator.close()


def test_orchestrator_passes_settings_models_dir_to_real_voice_preload(tmp_path, monkeypatch):
    from vericlue_ml.voice.challenge import VoiceChallengeDetector

    monkeypatch.setenv("MODELS_DIR", str(tmp_path / "wrong-env-root"))
    configured = tmp_path / "settings-root"
    captured = []

    class FakeASR:
        version = "synthetic@configured-root"

        def preload(self, *, models_dir=None, device=None):
            captured.append(models_dir)

    detector = VoiceChallengeDetector(asr=FakeASR())
    orchestrator = Orchestrator(
        Settings(models_dir=str(configured)),
        detector_factory=lambda module: (
            detector if Module(module) == Module.VOICE_CHALLENGE else FakeDetector(module)
        ),
    )
    try:
        orchestrator.start()
        assert captured == [configured]
        assert not orchestrator.failed_modules
    finally:
        orchestrator.close()


def test_three_concurrent_runs_wait_fifo_without_false_detector_errors():
    gate = threading.Barrier(4)
    activity = {"active": 0, "peak": 0}
    lock = threading.Lock()

    def slow(inp):
        with lock:
            activity["active"] += 1
            activity["peak"] = max(activity["peak"], activity["active"])
        try:
            time.sleep(1)
            return answer(Module.FACE_PAD, prob_attack=0)
        finally:
            with lock:
                activity["active"] -= 1

    detector = FakeDetector(Module.FACE_PAD, slow)
    instances = {module: FakeDetector(module) for module in Module}
    instances[Module.FACE_PAD] = detector
    orchestrator = Orchestrator(
        Settings(detector_timeout_seconds=4, detector_workers=9, detector_queue_size=3),
        detector_factory=lambda module: instances[Module(module)],
    )
    orchestrator.start()

    def invoke(index):
        gate.wait(timeout=3)
        return orchestrator.run([Module.FACE_PAD], session_id=f"fifo-{index}", scenario="genuine")

    try:
        with ThreadPoolExecutor(max_workers=3) as workers:
            futures = [workers.submit(invoke, index) for index in range(3)]
            gate.wait(timeout=3)
            started = time.perf_counter()
            results = [future.result(timeout=5)[Module.FACE_PAD] for future in futures]
            elapsed = time.perf_counter() - started
        assert all(result.status == Status.OK for result in results)
        assert detector.calls == 3 and activity["peak"] == 1
        assert 2.8 <= elapsed < 4, f"three serial 1s inferences took {elapsed:.3f}s"
    finally:
        orchestrator.close()


def test_three_concurrent_finalize_requests_all_pass_and_store_five_results(monkeypatch):
    def slow_face(inp):
        if not (inp.session_id or "").startswith("ses_demo_"):
            time.sleep(1)
        return MockDetector(Module.FACE_PAD).predict(inp)

    def factory(module, *, mock=None):
        return (
            FakeDetector(module, slow_face)
            if Module(module) == Module.FACE_PAD
            else MockDetector(module)
        )

    monkeypatch.setattr(orchestration, "get_detector", factory)
    with TestClient(create_app()) as client:
        sessions = [client.post("/v1/sessions").json() for _ in range(3)]
        gate = threading.Barrier(3)

        def finalize(body):
            gate.wait(timeout=3)
            return client.post(
                f"/v1/sessions/{body['session_id']}/finalize",
                headers={"Authorization": "Bearer " + body["token"]},
            )

        with ThreadPoolExecutor(max_workers=3) as workers:
            responses = list(workers.map(finalize, sessions))
        assert all(
            response.status_code == 200 and response.json() == {"status": "pass"}
            for response in responses
        )
        database = client.app.state.vericlue.database
        with database.sessions() as connection:
            for body in sessions:
                count = connection.scalar(
                    select(func.count())
                    .select_from(ModuleResultRow)
                    .where(ModuleResultRow.session_id == body["session_id"])
                )
                assert count == 5


@pytest.mark.parametrize("step", ["finalize", "voice"])
def test_sqlite_guarded_routes_pass_lock_timeout_and_consume_absolute_budget(monkeypatch, step):
    monkeypatch.setenv("INFERENCE_BUDGET_SECONDS", "0.25")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            body = client.post("/v1/sessions").json()
            sid = body["session_id"]
            root = client.app.state.vericlue
            headers = {"Authorization": "Bearer " + body["token"]}
            if step == "voice":
                with root.transaction() as state:
                    session = state.sessions.get(sid)
                    session.voice_requested = True
                    state.flow._new_prompt(session)
            transaction_arguments, runner_arguments = [], []
            real_transaction, real_run = root.transaction, root.orchestrator.run

            @contextmanager
            def spy_transaction(*, lock_timeout_seconds=None, inference_deadline=None):
                transaction_arguments.append((lock_timeout_seconds, inference_deadline))
                if inference_deadline is not None:
                    time.sleep(0.04)  # Work before inference must consume the same budget.
                with real_transaction(
                    lock_timeout_seconds=lock_timeout_seconds, inference_deadline=inference_deadline
                ) as state:
                    yield state

            def spy_run(*args, **kwargs):
                runner_arguments.append((kwargs.get("deadline"), time.perf_counter()))
                return real_run(*args, **kwargs)

            monkeypatch.setattr(root, "transaction", spy_transaction)
            monkeypatch.setattr(root.orchestrator, "run", spy_run)
            before = time.perf_counter()
            options = (
                {"files": {"audio": ("voice.wav", b"synthetic", "audio/wav")}}
                if step == "voice"
                else {}
            )
            response = client.post(f"/v1/sessions/{sid}/{step}", headers=headers, **options)
            assert response.status_code == 200 and response.json() == {"status": "pass"}
            timeout, deadline = transaction_arguments[-1]
            assert timeout == root.settings.db_lock_timeout_seconds
            assert before < deadline <= before + 0.3
            assert runner_arguments and runner_arguments[0][0] == deadline
            assert 0 < deadline - runner_arguments[0][1] < 0.23
            # Non-inference endpoints retain their original unguarded transaction policy.
            client.post(
                f"/v1/sessions/{sid}/signals",
                headers=headers,
                json={"color_events": [], "frame_times": []},
            )
            assert transaction_arguments[-1] == (None, None)
    finally:
        get_settings.cache_clear()


def test_queue_overflow_is_busy_and_expired_waiters_are_pruned_without_inference():
    entered, release = threading.Event(), threading.Event()
    predicted = []

    def action(inp):
        predicted.append(inp.session_id)
        if inp.session_id == "running":
            entered.set()
            assert release.wait(timeout=3)
        return answer(Module.FACE_PAD, prob_attack=0)

    instances = {module: FakeDetector(module) for module in Module}
    instances[Module.FACE_PAD] = FakeDetector(Module.FACE_PAD, action)
    orchestrator = Orchestrator(
        Settings(detector_timeout_seconds=2, detector_workers=9, detector_queue_size=3),
        detector_factory=lambda module: instances[Module(module)],
    )
    orchestrator.start()

    def invoke(identifier, deadline=None):
        return orchestrator.run(
            [Module.FACE_PAD], session_id=identifier, scenario="genuine", deadline=deadline
        )[Module.FACE_PAD]

    def wait_for_pending(count):
        limit = time.perf_counter() + 1
        while True:
            with orchestrator._lifecycle:
                actual = len(orchestrator._queues[Module.FACE_PAD])
            if actual == count:
                return
            assert time.perf_counter() < limit, f"expected {count} pending jobs, observed {actual}"
            time.sleep(0.002)

    try:
        with ThreadPoolExecutor(max_workers=5) as workers:
            running = workers.submit(invoke, "running")
            assert entered.wait(timeout=1)
            waiting = [
                workers.submit(invoke, f"expired-{index}", time.perf_counter() + 0.3)
                for index in range(3)
            ]
            try:
                wait_for_pending(3)
                overflow = invoke("overflow")
                assert (
                    overflow.status == Status.ERROR and overflow.error_code == ErrorCode.E_TIMEOUT
                )
                assert any(
                    item.name == "orchestration_reason" and item.value == "busy"
                    for item in overflow.evidence
                )
                for future in waiting:
                    result = future.result(timeout=1)
                    assert result.error_code == ErrorCode.E_TIMEOUT
                    assert any(
                        item.name == "orchestration_reason" and item.value == "timeout"
                        for item in result.evidence
                    )
                fresh = workers.submit(invoke, "fresh")
                wait_for_pending(1)  # Admission prunes all three expired waiters first.
                assert predicted == ["running"]
                release.set()
                assert fresh.result(timeout=1).status == Status.OK
                assert running.result(timeout=1).status == Status.OK
                assert predicted == ["running", "fresh"]
            finally:
                release.set()
    finally:
        release.set()
        orchestrator.close()


def test_orchestrator_injects_settings_models_dir_into_real_voice_spoof_preload(
    tmp_path, monkeypatch
):
    from vericlue_ml.voice.antispoof import AntiDeepfakeDetector

    captured = []

    class Backend:
        def preload(self, *, models_dir=None, device=None):
            captured.append(models_dir)

        def __call__(self, _waveform):
            raise AssertionError("startup must not infer anti-spoof audio")

    detector = AntiDeepfakeDetector(backend=Backend())
    configured = tmp_path / "settings-anti-models"
    monkeypatch.setenv("MODELS_DIR", str(tmp_path / "wrong-process-env"))
    orchestrator = Orchestrator(
        Settings(models_dir=str(configured)),
        detector_factory=lambda module: (
            detector if Module(module) == Module.VOICE_SPOOF else FakeDetector(module)
        ),
    )
    try:
        orchestrator.start()
        assert captured == [configured]
        assert not orchestrator.failed_modules
    finally:
        orchestrator.close()
