"""ModuleResult — định dạng kết quả chuẩn của MỌI bộ phát hiện.

Khớp hợp đồng `packages/contracts/schemas/module_result.schema.json`.
Test `ml/tests/test_contract_sync.py` bảo đảm hai bên không lệch nhau.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Module(StrEnum):
    QUALITY = "quality"
    FACE_PAD = "face_pad"
    FACE_DEEPFAKE = "face_deepfake"
    CHROMAPULSE = "chromapulse"
    CAMPROBE = "camprobe"
    VOICE_SPOOF = "voice_spoof"
    VOICE_CHALLENGE = "voice_challenge"
    LIPSYNC = "lipsync"
    PROVENANCE = "provenance"
    GAZE_TRACKING = "gaze_tracking"
    HEAD_TURN = "head_turn"
    FACE_MATCH = "face_match"
    FACE_CONTINUITY = "face_continuity"


class Status(StrEnum):
    OK = "ok"
    NOT_APPLICABLE = "not_applicable"  # không có mặt, im lặng, nhiều mặt...
    DEGRADED = "degraded"  # chạy được nhưng đầu vào kém — KHÔNG được coi là đạt
    ERROR = "error"  # lỗi — KHÔNG BAO GIỜ được coi là đạt


class ErrorCode(StrEnum):
    E_NO_FACE = "E_NO_FACE"
    E_MULTI_FACE = "E_MULTI_FACE"
    E_LOW_QUALITY = "E_LOW_QUALITY"
    E_TIMEOUT = "E_TIMEOUT"
    E_DECODE = "E_DECODE"
    E_CHALLENGE_MISMATCH = "E_CHALLENGE_MISMATCH"
    E_INTEGRITY = "E_INTEGRITY"
    E_INTERNAL = "E_INTERNAL"


class Gate(StrEnum):
    """Kết quả của cổng luật (quality, chromapulse, camprobe)."""

    PASS = "pass"
    FAIL = "fail"
    UNCLEAR = "unclear"


class EvidenceType(StrEnum):
    SCALAR = "scalar"
    TIMESERIES = "timeseries"
    IMAGE = "image"
    SEGMENTS = "segments"
    TEXT = "text"


class Evidence(BaseModel):
    """Một mẩu bằng chứng hiển thị cho người duyệt hoặc điều tra viên."""

    model_config = ConfigDict(extra="forbid")

    type: EvidenceType
    name: str
    value: Any = None
    uri: str | None = None
    unit: str | None = None
    label_vi: str | None = Field(default=None, description="Nhãn tiếng Việt cho người duyệt")


class ModuleResult(BaseModel):
    """Kết quả chuẩn của một bộ phát hiện. TrustRouter chỉ dùng `prob_attack`."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    module: Module
    model_version: str
    status: Status
    error_code: ErrorCode | None = None
    score: float | None = Field(default=None, description="Điểm thô, chưa hiệu chỉnh")
    prob_attack: float | None = Field(default=None, ge=0.0, le=1.0)
    gate: Gate | None = None
    quality: dict[str, float | str | bool | None] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    latency_ms: float = Field(ge=0.0)

    @property
    def is_usable(self) -> bool:
        """Có thể dùng làm bằng chứng cho phép 'đạt' hay không.

        error và degraded KHÔNG BAO GIỜ được coi là đạt (AGENTS.md §6 luật 4).
        """
        return self.status == Status.OK

    def to_contract(self) -> dict[str, Any]:
        """Dạng JSON đúng hợp đồng (bỏ trường None ngoài các trường bắt buộc)."""
        return self.model_dump(mode="json", exclude_none=True)
