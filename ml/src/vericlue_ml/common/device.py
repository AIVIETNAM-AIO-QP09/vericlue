"""Chọn thiết bị chạy mô hình (CPU hay GPU) một cách thống nhất cho mọi detector.

`DEVICE` (biến môi trường hoặc `Settings.device`) nhận `cpu` | `cuda` | `cuda:N` | `auto`:
- `cpu`: luôn CPU.
- `cuda` / `cuda:N` / `auto`: dùng GPU nếu có; KHÔNG có GPU (hoặc thiếu runtime) thì tự lùi về CPU và
  ghi log cảnh báo — không bao giờ làm phiên hỏng chỉ vì thiếu GPU.

Dùng chung cho torch (GenD, AntiDeepfake, PhoWhisper) và onnxruntime (SCRFD, MiniFASNet). Bản mặc định
và CI cài torch/onnxruntime CPU; GPU cần extra `cuda` (xem `ml/README.md`).
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger("vericlue_ml.device")

_VALID = re.compile(r"cpu|auto|cuda(?::\d+)?")


def requested_device(device: str | None = None, default: str = "cpu") -> str:
    """Giá trị đã chuẩn hóa: tham số > biến `DEVICE` > `default`. Sai định dạng thì ValueError."""
    value = (device or os.environ.get("DEVICE") or default).strip().lower()
    if not _VALID.fullmatch(value):
        raise ValueError("Thiết bị hợp lệ: cpu, cuda, cuda:N hoặc auto.")
    return value


def resolve_torch_device(
    device: str | None = None, *, component: str = "", default: str = "cpu"
) -> str:
    """`cpu` hoặc `cuda[:N]` cho torch; yêu cầu GPU mà không có thì lùi về CPU và ghi log."""
    wanted = requested_device(device, default)
    if wanted == "cpu":
        return "cpu"
    try:
        import torch

        available = torch.cuda.is_available()
    except Exception:  # noqa: BLE001 - thiếu torch hay lỗi driver đều coi như không có GPU
        available = False
    if not available:
        logger.warning(
            "device_fallback component=%s requested=%s used=cpu reason=torch_cuda_unavailable",
            component,
            wanted,
        )
        return "cpu"
    return "cuda" if wanted == "auto" else wanted


def preload_onnx_cuda_dlls() -> None:
    """Nạp DLL CUDA/cuDNN cho onnxruntime-gpu (gói pip `nvidia-*` hoặc đi kèm torch). Lỗi thì bỏ qua."""
    try:
        import onnxruntime as ort

        preload = getattr(ort, "preload_dlls", None)
        if preload is not None:
            preload()
    except Exception as exc:  # noqa: BLE001
        logger.warning("onnx_preload_dlls_failed error=%s", type(exc).__name__)


def onnx_providers(device: str | None = None, *, component: str = "") -> list[str]:
    """Danh sách execution provider cho onnxruntime; CPU luôn có để lùi về."""
    import onnxruntime as ort

    wanted = requested_device(device)
    if wanted == "cpu":
        return ["CPUExecutionProvider"]
    preload_onnx_cuda_dlls()
    if "CUDAExecutionProvider" in ort.get_available_providers():
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    logger.warning(
        "device_fallback component=%s requested=%s used=cpu reason=onnxruntime_without_cuda",
        component,
        wanted,
    )
    return ["CPUExecutionProvider"]


def check_onnx_session(session, device: str | None, *, component: str = "") -> str:
    """Provider thực sự đang chạy; ghi log nếu yêu cầu GPU mà phiên đã lùi về CPU."""
    active = session.get_providers()[0]
    if requested_device(device) != "cpu" and active != "CUDAExecutionProvider":
        logger.warning(
            "device_fallback component=%s requested=%s used=cpu reason=cuda_provider_not_loaded",
            component,
            requested_device(device),
        )
    return active
