"""Giai đoạn A của luồng eKYC (ADR-0013): OTP mô phỏng (FLOW-02) và nhận CCCD (FLOW-03).

Không lưu số điện thoại hay số CCCD dạng rõ: chỉ HMAC (để kiểm "đã đăng ký" sau này) và mã OTP băm.
Phát hiện thẻ giả nằm ngoài phạm vi; ở đây chỉ kiểm định dạng QR.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.schemas.session import (
    IdCardConfirmResponse,
    IdCardFields,
    IdCardResponse,
    OtpSent,
    OtpVerifyResponse,
)
from vericlue_api.services.session_store import Session


class OtpChannel(Protocol):
    """Kênh gửi mã. Trả nội dung tin nhắn để app hiện khi kênh là mô phỏng; kênh thật trả None."""

    def send(self, phone: str, code: str) -> str | None: ...


class SimulatedSms:
    """Bản demo: không gửi tin thật, app hiện tin nhắn trong khung "SMS mô phỏng"."""

    def send(self, phone: str, code: str) -> str | None:
        return f"VeriClue: Mã xác minh của bạn là {code}. Mã hết hạn sau 2 phút."


def _digest(key: str, value: str) -> str:
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


class IdentitySteps:
    def __init__(self, settings: Settings, channel: OtpChannel | None = None) -> None:
        self.settings = settings
        self.channel = channel or SimulatedSms()

    def _key(self) -> str:
        return self.settings.id_hmac_key.get_secret_value()

    # --- OTP ---------------------------------------------------------------
    def send_otp(self, session: Session, phone: str) -> OtpSent:
        if session.otp_verified:
            raise ApiError(409, "otp_already_verified", "Số điện thoại đã được xác minh.")
        code = f"{secrets.randbelow(10**6):06d}"
        session.phone_hmac = _digest(self._key(), phone)
        session.otp_hash = _digest(self._key(), f"{session.session_id}:{code}")
        session.otp_expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.otp_ttl_seconds
        )
        session.otp_attempts_left = self.settings.otp_max_attempts
        return OtpSent(
            expires_at=session.otp_expires_at,
            attempts_left=session.otp_attempts_left,
            simulated_sms=self.channel.send(phone, code),
        )

    def verify_otp(self, session: Session, code: str) -> OtpVerifyResponse:
        if session.otp_verified:
            raise ApiError(409, "otp_already_verified", "Mã đã được dùng.")
        if session.otp_hash is None or session.otp_expires_at is None:
            raise ApiError(409, "otp_not_requested", "Chưa yêu cầu gửi mã.")
        if session.otp_attempts_left <= 0:
            raise ApiError(409, "otp_locked", "Nhập sai quá số lần. Hãy yêu cầu mã mới.")
        if datetime.now(UTC) >= session.otp_expires_at:
            raise ApiError(409, "otp_expired", "Mã đã hết hạn. Hãy yêu cầu mã mới.")
        expected = _digest(self._key(), f"{session.session_id}:{code}")
        if hmac.compare_digest(expected, session.otp_hash):
            session.otp_verified = True
            session.otp_hash = None  # mã chỉ dùng một lần
            return OtpVerifyResponse(status="pass", attempts_left=session.otp_attempts_left)
        session.otp_attempts_left -= 1
        return OtpVerifyResponse(status="retry", attempts_left=session.otp_attempts_left)

    # --- CCCD --------------------------------------------------------------
    def accept_id_card(self, session: Session, qr: str | None) -> IdCardResponse:
        if not qr or not qr.strip():
            return IdCardResponse(status="retry", retry_hint="QR_UNREADABLE")
        fields = parse_cccd_qr(qr)
        if fields is None:
            return IdCardResponse(status="retry", retry_hint="QR_INVALID")
        session.id_fields = fields.model_dump(mode="json", exclude_none=True)
        session.id_number_hmac = _digest(self._key(), fields.id_number or "")
        return IdCardResponse(status="ok", fields=fields)

    def confirm_id_card(self, session: Session, confirmed: IdCardFields) -> IdCardConfirmResponse:
        """Người dùng xác nhận (hoặc sửa) thông tin; trường khác QR được ghi chú cho ca duyệt."""
        if session.id_fields is None:
            raise ApiError(409, "id_card_not_received", "Chưa nhận ảnh CCCD.")
        given = confirmed.model_dump(mode="json", exclude_none=True)
        session.id_edited = sorted(k for k, v in given.items() if session.id_fields.get(k) != v)
        return IdCardConfirmResponse()


def _ddmmyyyy(value: str) -> date | None:
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[4:]), int(value[2:4]), int(value[:2]))
    except ValueError:
        return None


def parse_cccd_qr(text: str) -> IdCardFields | None:
    """QR CCCD gắn chip: `số CCCD|số CMND cũ|họ tên|ngày sinh|giới tính|địa chỉ|ngày cấp` (ngày dạng ddmmyyyy).

    Trả None nếu sai định dạng. Thứ tự trường cần kiểm lại với thẻ thật (chỉ thử với dữ liệu tổng hợp).
    """
    parts = [p.strip() for p in text.strip().split("|")]
    if len(parts) < 6:
        return None
    id_number, _old_id, name, dob, sex, address = parts[:6]
    issued = parts[6] if len(parts) > 6 else ""
    born = _ddmmyyyy(dob)
    if len(id_number) != 12 or not id_number.isdigit() or not name or born is None:
        return None
    if sex not in ("Nam", "Nữ"):
        return None
    return IdCardFields(
        full_name=name,
        id_number=id_number,
        date_of_birth=born,
        sex=sex,
        address=address or None,
        issued_on=_ddmmyyyy(issued),
    )
