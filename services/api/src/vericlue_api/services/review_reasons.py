"""Mã lý do cho quyết định cuối của bàn duyệt.

DANH SÁCH TẠM — M2 chỉnh. Thêm/bớt mã chỉ sửa ở đây; schema giữ `reason_code` là chuỗi tự do,
API kiểm theo danh sách này (422 `invalid_reason_code`).
"""

from __future__ import annotations

from dataclasses import dataclass

NOTE_REQUIRED_CODE = "OTHER"


@dataclass(frozen=True)
class ReasonCode:
    code: str
    label: str
    note_required: bool = False


REASON_CODES: tuple[ReasonCode, ...] = (
    ReasonCode("AI_AGREES", "Đồng ý với ý kiến AI"),
    ReasonCode("AI_OVERRIDDEN", "Không đồng ý với ý kiến AI, dựa trên xem xét hồ sơ"),
    ReasonCode("SPOOF_CONFIRMED", "Xác nhận có dấu hiệu giả mạo trong hồ sơ"),
    ReasonCode("GENUINE_CONFIRMED", "Xác nhận hồ sơ là người thật"),
    ReasonCode("POOR_CAPTURE", "Chất lượng ảnh/video kém, cần chụp lại"),
    ReasonCode("VOICE_MISMATCH", "Giọng nói không khớp hoặc nghi ngờ"),
    ReasonCode("DOCUMENT_MISMATCH", "Khuôn mặt không khớp giấy tờ"),
    ReasonCode("SYSTEM_DEGRADED", "Hệ thống lỗi hoặc thiếu kết quả AI, không đủ căn cứ"),
    ReasonCode(NOTE_REQUIRED_CODE, "Lý do khác (bắt buộc ghi chú)", note_required=True),
)

_BY_CODE = {r.code: r for r in REASON_CODES}


def get_reason(code: str) -> ReasonCode | None:
    return _BY_CODE.get(code)
