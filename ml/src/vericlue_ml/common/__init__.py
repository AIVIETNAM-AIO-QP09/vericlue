"""Thành phần dùng chung: định dạng kết quả, giao diện bộ phát hiện."""

from vericlue_ml.common.detector import Detector, DetectorInput
from vericlue_ml.common.result import (
    ErrorCode,
    Evidence,
    EvidenceType,
    Gate,
    Module,
    ModuleResult,
    Status,
)

__all__ = [
    "Detector",
    "DetectorInput",
    "ErrorCode",
    "Evidence",
    "EvidenceType",
    "Gate",
    "Module",
    "ModuleResult",
    "Status",
]
