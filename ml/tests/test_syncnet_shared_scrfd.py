"""SyncNet shares PAD's SCRFD session while preserving its default preprocessing."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.face import pad
from vericlue_ml.voice import syncnet


@pytest.fixture
def shared_session(monkeypatch):
    verified, created = [], []

    class FakeSession:
        def __init__(self):
            self.feeds = []

        def get_inputs(self):
            return [SimpleNamespace(name="input")]

        def get_outputs(self):
            return [SimpleNamespace(name=f"output-{index}") for index in range(9)]

        def run(self, outputs, feed):
            self.feeds.append(feed["input"])
            return (
                [np.zeros((1, 1), dtype=np.float32) for _ in range(3)]
                + [np.zeros((1, 4), dtype=np.float32) for _ in range(3)]
                + [np.zeros((1, 10), dtype=np.float32) for _ in range(3)]
            )

    def weights(root, module, filename):
        verified.append((root, module, filename))
        assert (module, filename) == (pad.DETECTOR_MODEL_ID, pad.DETECTOR_FILE)
        return root / module / filename, "verified-revision"

    def session(path, device):
        instance = FakeSession()
        created.append((path, device, instance))
        return instance

    monkeypatch.setattr(pad, "_SCRFD_SESSIONS", {})
    monkeypatch.setattr(pad, "_verified_weights", weights)
    monkeypatch.setattr(pad, "_session", session)
    monkeypatch.setattr(syncnet, "_manifest_entry", lambda *args: {"revision": "a" * 40})
    return verified, created


def detector(root):
    aligner_calls, backend_calls = [], []
    aligner = SimpleNamespace(preload=lambda **kwargs: aligner_calls.append(kwargs))
    backend = SimpleNamespace(preload=lambda **kwargs: backend_calls.append(kwargs))
    instance = syncnet.SyncNetDetector(models_dir=root, aligner=aligner, backend=backend)
    return instance, aligner_calls, backend_calls


def test_two_syncnet_detectors_reuse_pad_session_and_keep_default_normalization(
    shared_session, monkeypatch
):
    verified, created = shared_session
    root = Path("unopened-model-root").resolve()
    first, first_aligner, first_backend = detector(root)
    second, second_aligner, second_backend = detector(root)
    first.preload(models_dir=root, device="cpu")
    first.preload(models_dir=root, device="cpu")
    second.preload(models_dir=root, device="cpu")
    second.preload(models_dir=root, device="cpu")

    assert verified == [(root, pad.DETECTOR_MODEL_ID, pad.DETECTOR_FILE)]
    assert len(created) == 1
    shared = created[0][2]
    assert pad.shared_scrfd_session(root, "cpu") == (shared, "verified-revision")
    assert first._finder is not second._finder
    assert isinstance(first._finder, pad.ScrfdFaceFinder)
    assert isinstance(second._finder, pad.ScrfdFaceFinder)
    assert first._finder._session is second._finder._session is shared
    for calls in (first_aligner, first_backend, second_aligner, second_backend):
        assert calls == [{"models_dir": root, "device": "cpu"}]

    image = np.array([[[0, 64, 255], [10, 100, 200]]], dtype=np.uint8)
    monkeypatch.setattr(pad, "_letterbox", lambda values, size: (values, 1.0))
    assert first._finder.find(image) == second._finder.find(image) == []
    expected = ((image.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
    assert len(shared.feeds) == 2
    for tensor in shared.feeds:
        np.testing.assert_array_equal(tensor, expected)


@pytest.mark.parametrize("changed", ["root", "device"])
def test_loaded_syncnet_requires_restart_when_root_or_device_changes(shared_session, changed):
    verified, created = shared_session
    root = Path("unopened-model-root").resolve()
    instance, aligner_calls, backend_calls = detector(root)
    instance.preload(models_dir=root, device="cpu")
    with pytest.raises(syncnet.SyncNetError, match="restart"):
        instance.preload(
            models_dir=root / "different" if changed == "root" else root,
            device="cuda:0" if changed == "device" else "cpu",
        )
    assert len(verified) == len(created) == 1
    assert len(aligner_calls) == len(backend_calls) == 1


def test_auto_reuses_pad_cache_and_predict_preloads_with_the_original_request(
    shared_session, monkeypatch
):
    verified, created = shared_session
    root = Path("unopened-model-root").resolve()
    shared, _ = pad.shared_scrfd_session(root, "auto")
    resolutions = []

    def resolve(requested, **kwargs):
        resolutions.append(requested)
        return "cpu"

    monkeypatch.setattr(syncnet, "resolve_torch_device", resolve)
    instance, aligner_calls, backend_calls = detector(root)
    instance.preload(models_dir=root, device="auto")
    instance.preload(models_dir=root, device="auto")
    assert resolutions and all(requested == "auto" for requested in resolutions)
    assert len(verified) == len(created) == 1
    assert created[0][1] == "auto"
    assert instance._finder._session is shared
    assert aligner_calls == backend_calls == [{"models_dir": root, "device": "cpu"}]

    preload_calls, alignment_calls = [], []
    original_preload = instance.preload

    def preload(**kwargs):
        preload_calls.append(kwargs)
        return original_preload(**kwargs)

    def stop_after_alignment(audio, prompt):
        alignment_calls.append((audio, prompt))
        raise syncnet.SyncNetError("Stop synthetic pipeline before media access")

    monkeypatch.setattr(instance, "preload", preload)
    instance._aligner.align = stop_after_alignment
    inp = DetectorInput(
        audio=Path("unopened.wav"),
        video=Path("unopened.mp4"),
        metadata={"prompt": "câu đề bài"},
    )
    instance.predict(inp)
    assert preload_calls == [{"models_dir": root, "device": "auto"}]
    assert alignment_calls == [(inp.audio, inp.metadata["prompt"])]
    assert len(verified) == len(created) == 1


def test_unavailable_cuda_uses_common_cpu_fallback_and_preserves_raw_onnx_request(
    shared_session, monkeypatch, caplog
):
    verified, created = shared_session
    root = Path("unopened-model-root").resolve()
    resolutions = []

    def resolve(requested, **kwargs):
        resolutions.append(requested)
        logging.getLogger("vericlue_ml.device").warning(
            "device_fallback requested=%s used=cpu reason=torch_cuda_unavailable", requested
        )
        return "cpu"

    monkeypatch.setattr(syncnet, "resolve_torch_device", resolve)
    instance, aligner_calls, backend_calls = detector(root)
    with caplog.at_level(logging.WARNING, logger="vericlue_ml.device"):
        instance.preload(models_dir=root, device="cuda")
    assert resolutions == ["cuda"]
    assert created[0][1] == "cuda"
    assert aligner_calls == backend_calls == [{"models_dir": root, "device": "cpu"}]
    assert "device_fallback" in caplog.text and "used=cpu" in caplog.text
    assert len(verified) == len(created) == 1


def test_changing_auto_to_explicit_cpu_requires_restart_even_when_both_resolve_to_cpu(
    shared_session, monkeypatch
):
    verified, created = shared_session
    monkeypatch.setattr(syncnet, "resolve_torch_device", lambda requested, **kwargs: "cpu")
    root = Path("unopened-model-root").resolve()
    instance, aligner_calls, backend_calls = detector(root)
    instance.preload(models_dir=root, device="auto")
    with pytest.raises(syncnet.SyncNetError, match="restart"):
        instance.preload(models_dir=root, device="cpu")
    assert len(verified) == len(created) == 1
    assert len(aligner_calls) == len(backend_calls) == 1
