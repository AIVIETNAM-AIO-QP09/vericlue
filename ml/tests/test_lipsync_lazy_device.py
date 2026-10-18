"""Lipsync owns its lazy device configuration; no test loads models or media."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Status
from vericlue_ml.voice import syncnet


@pytest.fixture
def lazy_pipeline(monkeypatch):
    calls = {name: [] for name in ("resolve", "aligner", "scrfd", "finder", "backend", "align")}
    failure = {"stage": None}
    resolved = {"device": "cpu"}
    finder = object()
    alignment = SimpleNamespace(
        splice_events=[],
        syllables=[],
        aligned_segments=[SimpleNamespace(start_s=0.0, end_s=4.0)],
    )

    def record(stage, value):
        calls[stage].append(value)
        if failure["stage"] == stage:
            raise RuntimeError(f"Synthetic {stage} load failure")

    def resolve(wanted, **kwargs):
        record("resolve", wanted)
        return resolved["device"]

    def shared(root, wanted):
        record("scrfd", (root, wanted))
        return "fake-onnx-session", "revision"

    def make_finder(session):
        record("finder", session)
        return finder

    def align(audio, prompt):
        record("align", (audio, prompt))
        return alignment

    def read_windows(video, starts, received_finder):
        assert received_finder is finder
        return [[np.zeros((2, 2, 3), dtype=np.uint8)] * 16 for _ in starts]

    monkeypatch.setattr(syncnet, "_manifest_entry", lambda *args: {"revision": "a" * 40})
    monkeypatch.setattr(syncnet, "resolve_torch_device", resolve)
    monkeypatch.setattr(syncnet, "shared_scrfd_session", shared)
    monkeypatch.setattr(syncnet, "ScrfdFaceFinder", make_finder)
    monkeypatch.setattr(syncnet, "_read_windows", read_windows)
    monkeypatch.setattr(syncnet, "load_audio", lambda path: np.zeros(64000, dtype=np.float32))
    monkeypatch.setattr(
        syncnet, "_mel_spectrogram", lambda audio: np.zeros((80, 500), dtype=np.float32)
    )

    def make_detector(**kwargs):
        aligner = SimpleNamespace(
            preload=lambda **options: record("aligner", options),
            align=align,
        )
        backend = SimpleNamespace(
            preload=lambda **options: record("backend", options),
            embed_video=lambda crops: np.array([1.0, 0.0]),
            embed_audio_batch=lambda mels: np.tile([1.0, 0.0], (len(mels), 1)),
        )
        return syncnet.SyncNetDetector(aligner=aligner, backend=backend, **kwargs)

    return make_detector, calls, failure, resolved


def input_with_video():
    return DetectorInput(
        audio=Path("unopened.wav"),
        video=Path("unopened.mp4"),
        metadata={"prompt": "câu đề bài"},
    )


def test_constructor_defaults_to_cpu_independently_of_global_device(lazy_pipeline, monkeypatch):
    monkeypatch.setenv("DEVICE", "cuda")
    monkeypatch.setenv("LIPSYNC_DEVICE", "cuda")
    make_detector, calls, _, _ = lazy_pipeline
    detector = make_detector()
    assert detector._requested_device == "cpu"
    assert detector._device == "cpu"
    assert not detector._loaded
    assert all(not values for values in calls.values())


@pytest.mark.parametrize("requested", ["cpu", "cuda", "auto"])
def test_configure_does_not_resolve_or_load_any_model(lazy_pipeline, requested):
    make_detector, calls, _, _ = lazy_pipeline
    detector = make_detector()
    configured = Path("unopened-configured-root").resolve()
    detector.configure(models_dir=configured, device=requested)
    detector.configure(models_dir=configured, device=requested)
    assert detector._root == configured
    assert detector._requested_device == requested
    assert not detector._loaded
    assert all(not values for values in calls.values())


@pytest.mark.parametrize(
    "requested,resolved_device", [("cpu", "cpu"), ("auto", "cpu"), ("cuda", "cuda:0")]
)
def test_first_predict_loads_only_the_lipsync_devices_once(
    lazy_pipeline, requested, resolved_device, monkeypatch
):
    monkeypatch.setenv("DEVICE", "cuda:7")
    make_detector, calls, _, resolved = lazy_pipeline
    resolved["device"] = resolved_device
    root = Path("unopened-lipsync-root").resolve()
    detector = make_detector()
    detector.configure(models_dir=root, device=requested)
    assert all(not values for values in calls.values())
    first = detector.predict(input_with_video())
    second = detector.predict(input_with_video())
    assert first.status == second.status == Status.OK
    assert first.score == second.score == 0
    assert calls["resolve"] == [requested]
    assert calls["scrfd"] == [(root, requested)]
    assert calls["finder"] == ["fake-onnx-session"]
    assert calls["aligner"] == calls["backend"] == [{"models_dir": root, "device": resolved_device}]
    assert len(calls["align"]) == 2
    assert detector._loaded


def test_no_video_does_not_trigger_lazy_model_loading(lazy_pipeline):
    make_detector, calls, _, _ = lazy_pipeline
    detector = make_detector(device="cuda")
    result = detector.predict(input_with_video().model_copy(update={"video": None}))
    assert result.status == Status.NOT_APPLICABLE
    assert result.score is result.prob_attack is None
    assert not detector._loaded and not detector._load_failed
    assert all(not values for values in calls.values())


@pytest.mark.parametrize("stage", ["resolve", "aligner", "scrfd", "backend"])
def test_failed_lazy_load_is_sticky_and_repeated_predict_cannot_pass(lazy_pipeline, stage):
    make_detector, calls, failure, _ = lazy_pipeline
    detector = make_detector()
    failure["stage"] = stage
    first = detector.predict(input_with_video())
    first_calls = {name: list(values) for name, values in calls.items()}
    failure["stage"] = None  # Availability recovering must not silently retry a partial load.
    second = detector.predict(input_with_video())
    assert first.status == second.status == Status.ERROR
    assert first.error_code == second.error_code == ErrorCode.E_INTERNAL
    assert first.score is first.prob_attack is second.score is second.prob_attack is None
    assert calls == first_calls
    assert detector._load_failed and not detector._loaded
    assert not calls["align"]
    with pytest.raises(syncnet.SyncNetError, match="restart"):
        detector.configure(device="cuda")


@pytest.mark.parametrize("configured", [None, "cpu", "cuda", "auto"])
def test_registry_uses_only_lipsync_device_and_defaults_to_cpu(monkeypatch, configured):
    from vericlue_ml import registry

    monkeypatch.setenv("DEVICE", "cuda")
    if configured is None:
        monkeypatch.delenv("LIPSYNC_DEVICE", raising=False)
    else:
        monkeypatch.setenv("LIPSYNC_DEVICE", configured)
    captured = []
    instance = object()

    def construct(**kwargs):
        captured.append(kwargs)
        return instance

    monkeypatch.setattr(syncnet, "SyncNetDetector", construct)
    registry._lipsync.cache_clear()
    try:
        assert registry._lipsync() is registry._lipsync() is instance
        assert captured == [{"device": configured or "cpu"}]
    finally:
        registry._lipsync.cache_clear()
