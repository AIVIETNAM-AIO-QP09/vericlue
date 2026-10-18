"""Chọn thiết bị (CPU/GPU) và khớp extra `cuda` với `face` + `voice` — không cần GPU."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

import pytest

from vericlue_ml.common import device

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_requested_device_prefers_argument_then_env_then_default(monkeypatch):
    monkeypatch.delenv("DEVICE", raising=False)
    assert device.requested_device() == "cpu"
    monkeypatch.setenv("DEVICE", "CUDA")
    assert device.requested_device() == "cuda"
    assert device.requested_device("cpu") == "cpu"
    assert device.requested_device("cuda:1") == "cuda:1"


@pytest.mark.parametrize("bad", ["gpu", "cuda:", "cuda:x", "tpu"])
def test_requested_device_rejects_unknown_values(bad):
    with pytest.raises(ValueError):
        device.requested_device(bad)


def test_torch_cpu_never_touches_cuda(monkeypatch):
    monkeypatch.delenv("DEVICE", raising=False)
    assert device.resolve_torch_device("cpu") == "cpu"


def test_torch_falls_back_to_cpu_and_logs_when_cuda_unavailable(monkeypatch, caplog):
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with caplog.at_level(logging.WARNING, logger="vericlue_ml.device"):
        assert device.resolve_torch_device("cuda", component="t") == "cpu"
        assert device.resolve_torch_device("auto", component="t") == "cpu"
    assert "device_fallback component=t requested=cuda used=cpu" in caplog.text


def test_torch_uses_cuda_when_available(monkeypatch):
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert device.resolve_torch_device("cuda") == "cuda"
    assert device.resolve_torch_device("auto") == "cuda"
    assert device.resolve_torch_device("cuda:1") == "cuda:1"


def test_onnx_providers_cpu_and_fallback(monkeypatch, caplog):
    ort = pytest.importorskip("onnxruntime")
    assert device.onnx_providers("cpu") == ["CPUExecutionProvider"]
    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CPUExecutionProvider"])
    with caplog.at_level(logging.WARNING, logger="vericlue_ml.device"):
        assert device.onnx_providers("cuda", component="s") == ["CPUExecutionProvider"]
    assert "onnxruntime_without_cuda" in caplog.text


def test_onnx_providers_prefer_cuda_when_present(monkeypatch):
    ort = pytest.importorskip("onnxruntime")
    monkeypatch.setattr(
        ort, "get_available_providers", lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    )
    monkeypatch.setattr(device, "preload_onnx_cuda_dlls", lambda: None)
    assert device.onnx_providers("auto") == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_check_onnx_session_logs_when_gpu_requested_but_cpu_active(caplog):
    class Session:
        def get_providers(self):
            return ["CPUExecutionProvider"]

    with caplog.at_level(logging.WARNING, logger="vericlue_ml.device"):
        assert device.check_onnx_session(Session(), "cuda", component="x") == "CPUExecutionProvider"
    assert "cuda_provider_not_loaded" in caplog.text


def _names(requirements):
    import re

    return {re.split(r"[\[<>=!~ ]", r, maxsplit=1)[0] for r in requirements}


def test_cuda_extra_is_face_plus_voice_with_gpu_onnxruntime():
    extras = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"][
        "optional-dependencies"
    ]
    cpu = _names(extras["face"]) | _names(extras["voice"])
    gpu = _names(extras["cuda"])
    assert gpu == (cpu - {"onnxruntime"}) | {"onnxruntime-gpu"}
