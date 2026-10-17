"""Danh bạ bộ phát hiện: trả mock hoặc mô hình thật tùy `USE_MOCK_MODELS`.

Khi một task mô hình thật xong (ví dụ FACE-02), đăng ký vào `_REAL_FACTORIES`
và cập nhật `ml/configs/models.yaml`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache

from vericlue_ml.common.detector import Detector
from vericlue_ml.common.result import Module
from vericlue_ml.mock import MOCK_DETECTORS

# Module → task sẽ làm mô hình thật (để thông báo lỗi chỉ đúng chỗ).
REAL_TASK: dict[Module, str] = {
    Module.QUALITY: "CAP-02 / PRES-02",
    Module.FACE_PAD: "FACE-01",
    Module.FACE_DEEPFAKE: "FACE-02",
    Module.CHROMAPULSE: "PRES-02",
    Module.CAMPROBE: "PRES-03",
    Module.VOICE_SPOOF: "VOICE-01",
    Module.VOICE_CHALLENGE: "VOICE-04",
    Module.LIPSYNC: "VOICE-05",
    Module.PROVENANCE: "FOR-03",
}


# Module → hàm tạo mô hình thật. Các task mô hình đăng ký vào đây.
@lru_cache(maxsize=1)
def _voice_challenge() -> Detector:
    from vericlue_ml.voice.challenge import VoiceChallengeDetector

    return VoiceChallengeDetector()


@lru_cache(maxsize=1)
def _voice_spoof() -> Detector:
    from vericlue_ml.voice.antispoof import AntiDeepfakeDetector

    return AntiDeepfakeDetector()


_REAL_FACTORIES: dict[Module, Callable[[], Detector]] = {
    Module.VOICE_CHALLENGE: _voice_challenge,
    Module.VOICE_SPOOF: _voice_spoof,
}


def use_mock_models() -> bool:
    """Đọc `USE_MOCK_MODELS` (mặc định true — chạy được ngay khi chưa có mô hình)."""
    return os.getenv("USE_MOCK_MODELS", "true").strip().lower() in {"1", "true", "yes", "on"}


def get_detector(name: str | Module, *, mock: bool | None = None) -> Detector:
    """Trả bộ phát hiện cho `name`. `mock=None` thì theo biến môi trường."""
    module = Module(name)
    if mock if mock is not None else use_mock_models():
        return MOCK_DETECTORS[module]
    factory = _REAL_FACTORIES.get(module)
    if factory is None:
        raise NotImplementedError(
            f"Chưa có mô hình thật cho '{module.value}' (task {REAL_TASK[module]}). "
            "Đặt USE_MOCK_MODELS=true để dùng mô-đun giả lập."
        )
    return factory()


def register(module: Module, factory: Callable[[], Detector]) -> None:
    """Đăng ký mô hình thật cho một module."""
    _REAL_FACTORIES[Module(module)] = factory
