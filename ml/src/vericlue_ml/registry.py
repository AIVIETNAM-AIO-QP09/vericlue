"""Danh bạ bộ phát hiện: trả mock hoặc mô hình thật tùy `USE_MOCK_MODELS`.

`USE_MOCK_MODELS` có ba giá trị: `true` (mọi module mock), `false` (mọi module thật; module chưa có
mô hình thật thì lỗi), `mixed` (module có trong `_REAL_FACTORIES` dùng thật, còn lại dùng mock).

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
    Module.QUALITY: "FACE-02 (MVP, ADR-0012)",
    Module.FACE_PAD: "FACE-01",
    Module.FACE_DEEPFAKE: "FACE-02",
    Module.CHROMAPULSE: "PRES-02",
    Module.CAMPROBE: "PRES-03",
    Module.VOICE_SPOOF: "VOICE-01",
    Module.VOICE_CHALLENGE: "VOICE-04",
    Module.LIPSYNC: "VOICE-05",
    Module.PROVENANCE: "FOR-03",
    Module.GAZE_TRACKING: "LIVE-02",
    Module.HEAD_TURN: "FLOW-04",
    Module.FACE_MATCH: "FLOW-05",
}


# Module → hàm tạo mô hình thật. Các task mô hình đăng ký vào đây.
@lru_cache(maxsize=1)
def _gaze_tracking() -> Detector:
    from vericlue_ml.presence.gaze import GazeDetector

    return GazeDetector()


@lru_cache(maxsize=1)
def _head_turn() -> Detector:
    from vericlue_ml.presence.head_turn import HeadTurnDetector

    return HeadTurnDetector()


@lru_cache(maxsize=1)
def _face_match() -> Detector:
    from vericlue_ml.face.match import FaceMatchDetector

    return FaceMatchDetector()


@lru_cache(maxsize=1)
def _voice_challenge() -> Detector:
    from vericlue_ml.voice.challenge import VoiceChallengeDetector

    return VoiceChallengeDetector()


@lru_cache(maxsize=1)
def _voice_spoof() -> Detector:
    from vericlue_ml.voice.antispoof import AntiDeepfakeDetector

    return AntiDeepfakeDetector()


@lru_cache(maxsize=1)
def _face_pad() -> Detector:
    from vericlue_ml.face.pad import FacePadDetector

    return FacePadDetector()


@lru_cache(maxsize=1)
def _face_deepfake() -> Detector:
    from vericlue_ml.face.gend import FaceDeepfakeDetector

    return FaceDeepfakeDetector()


@lru_cache(maxsize=1)
def _quality() -> Detector:
    from vericlue_ml.face.quality import QualityDetector

    return QualityDetector()


@lru_cache(maxsize=1)
def _camprobe() -> Detector:
    from vericlue_ml.presence.camprobe import CamProbeDetector

    return CamProbeDetector()


@lru_cache(maxsize=1)
def _lipsync() -> Detector:
    from vericlue_ml.voice.syncnet import SyncNetDetector

    return SyncNetDetector(device=os.getenv("LIPSYNC_DEVICE", "cpu"))


@lru_cache(maxsize=1)
def _provenance() -> Detector:
    from vericlue_ml.forensic.provenance import ProvenanceDetector

    return ProvenanceDetector()


_REAL_FACTORIES: dict[Module, Callable[[], Detector]] = {
    Module.GAZE_TRACKING: _gaze_tracking,
    Module.HEAD_TURN: _head_turn,
    Module.FACE_MATCH: _face_match,
    Module.VOICE_CHALLENGE: _voice_challenge,
    Module.VOICE_SPOOF: _voice_spoof,
    Module.FACE_PAD: _face_pad,
    Module.CAMPROBE: _camprobe,
    Module.FACE_DEEPFAKE: _face_deepfake,
    Module.QUALITY: _quality,
    Module.LIPSYNC: _lipsync,
    Module.PROVENANCE: _provenance,
}


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
MIXED = "mixed"


def mock_mode() -> bool | str:
    """Đọc `USE_MOCK_MODELS`: True, False hoặc "mixed" (mặc định true)."""
    value = os.getenv("USE_MOCK_MODELS", "true").strip().lower()
    return MIXED if value == MIXED else value in TRUE_VALUES


def use_mock_models() -> bool:
    """Đọc `USE_MOCK_MODELS` (mặc định true). Chế độ `mixed` KHÔNG phải mock toàn phần."""
    return mock_mode() is True


def get_detector(name: str | Module, *, mock: bool | str | None = None) -> Detector:
    """Trả bộ phát hiện cho `name`. `mock=None` thì theo biến môi trường.

    `mock` nhận True, False hoặc "mixed" (module có mô hình thật thì dùng thật, còn lại mock).
    """
    module = Module(name)
    mode = mock_mode() if mock is None else mock
    if isinstance(mode, str):
        mode = MIXED if mode.strip().lower() == MIXED else mode.strip().lower() in TRUE_VALUES
    if mode == MIXED:
        mode = module not in _REAL_FACTORIES
    if mode:
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


@lru_cache(maxsize=2)
def get_fsvfm_pad(*, mock: bool = False) -> Detector:
    """Explicit diagnostic alternative; leave get_detector('face_pad') unchanged."""
    if mock:
        from vericlue_ml.mock.fsvfm import MockFsvfmPadDetector

        return MockFsvfmPadDetector()
    from vericlue_ml.face.fsvfm import FsvfmPadDetector

    return FsvfmPadDetector()


@lru_cache(maxsize=2)
def get_chromapulse_diagnostic(*, mock: bool = False) -> Detector:
    """Opt-in color measurements; keep HTTP real/mixed selection unchanged."""
    if mock:
        return MOCK_DETECTORS[Module.CHROMAPULSE]
    from vericlue_ml.presence.chromapulse import ChromaPulseDetector

    return ChromaPulseDetector()


@lru_cache(maxsize=2)
def get_qwen_voice_challenge(*, mock: bool = False) -> Detector:
    """Explicit Qwen diagnostic; preserve the HTTP PhoWhisper selection and its runtime."""
    if mock:
        return MOCK_DETECTORS[Module.VOICE_CHALLENGE]
    from vericlue_ml.voice.qwen_asr import QwenVoiceChallengeDetector

    return QwenVoiceChallengeDetector()


@lru_cache(maxsize=2)
def get_nes2net(*, mock: bool = False) -> Detector:
    """Opt-in raw voice diagnostic; keep the HTTP AntiDeepfake backend unchanged."""
    if mock:
        return MOCK_DETECTORS[Module.VOICE_SPOOF]
    from vericlue_ml.voice.nes2net import Nes2NetDetector

    return Nes2NetDetector()


@lru_cache(maxsize=2)
def get_nes2net_timeline(*, mock: bool = False) -> Detector:
    """Opt-in per-window NES2Net evidence; keep HTTP and first4s factories unchanged."""
    if mock:
        from vericlue_ml.mock.nes2net_timeline import MockNes2NetTimelineDetector

        return MockNes2NetTimelineDetector()
    from vericlue_ml.voice.nes2net_timeline import Nes2NetTimelineDetector

    return Nes2NetTimelineDetector()


@lru_cache(maxsize=2)
def get_reading_timing(*, mock: bool = False) -> Detector:
    """Explicit timing diagnostic; preserve the HTTP content/ASR backend."""
    if mock:
        from vericlue_ml.mock.reading_timing import MockReadingTimingDetector

        return MockReadingTimingDetector()
    from vericlue_ml.voice.reading_timing import ReadingTimingDetector

    return ReadingTimingDetector()


@lru_cache(maxsize=2)
def get_ram_lipsync(*, mock: bool = False) -> Detector:
    """Explicit one-container lab backend; keep HTTP SyncNet selection unchanged."""
    if mock:
        from vericlue_ml.mock.av_lipsync import MockRamLipSyncDetector

        return MockRamLipSyncDetector()
    from vericlue_ml.voice.av_lipsync import RamLipSyncDetector

    return RamLipSyncDetector()
