"""Giai đoạn A của luồng eKYC (ADR-0013): OTP mô phỏng (FLOW-02) và nhận CCCD (FLOW-03).

Số điện thoại chỉ lưu HMAC, OTP lưu băm. CCCD dùng HMAC để tra cứu; số đầy đủ
chỉ được giữ trong snapshot đã mã hóa khi bật SEC-01, phục vụ nhân viên duyệt.
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
from vericlue_api.core.security_profile import ensure_otp_available
from vericlue_api.schemas.session import (
    IdCardConfirmResponse,
    IdCardFields,
    IdCardResponse,
    OtpSent,
    OtpVerifyResponse,
)
from vericlue_api.services.identity_runtime import IdentityRuntime
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import Session
from vericlue_api.services.storage import save_upload
from vericlue_ml.common.result import Module


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
    def __init__(
        self,
        settings: Settings,
        channel: OtpChannel | None = None,
        *,
        privacy: SessionPrivacy | None = None,
    ) -> None:
        self.settings = settings
        self.channel = channel or SimulatedSms()
        self.privacy = privacy

    def _key(self) -> str:
        return self.settings.id_hmac_key.get_secret_value()

    # --- OTP ---------------------------------------------------------------
    def send_otp(self, session: Session, phone: str) -> OtpSent:
        ensure_otp_available(self.settings)
        if session.otp_verified:
            raise ApiError(409, "otp_already_verified", "Số điện thoại đã được xác minh.")
        if session.otp_sends >= self.settings.otp_max_sends:
            raise ApiError(409, "otp_too_many", "Đã gửi mã quá số lần. Hãy bắt đầu lại.")
        session.otp_sends += 1
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
        ensure_otp_available(self.settings)
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
    @staticmethod
    def ensure_card_upload_allowed(session: Session) -> None:
        """Reject card changes before reading, scanning or storing new images."""
        if session.account_id:
            raise ApiError(409, "step_not_allowed", "Bước này chưa phù hợp.")
        if session.accepted_steps or session.face_scored:
            raise ApiError(409, "step_not_allowed", "Hãy bắt đầu lại phiên trước khi đổi ảnh thẻ.")

    def accept_images(
        self,
        session: Session,
        front: bytes,
        back: bytes,
        client_qr: str | None,
        *,
        front_filename: str | None = None,
        back_filename: str | None = None,
    ) -> IdCardResponse:
        self.ensure_card_upload_allowed(session)
        response = self._scan_images(session, front, back, client_qr)
        # Never overwrite a committed reference: DB rollback cannot undo file writes.
        # Unreferenced files from a failed write/commit are left to the session TTL cleanup.
        scan_id = secrets.token_hex(16)
        front_path = save_upload(
            self.settings.media_dir,
            session.session_id,
            f"id_front_{scan_id}",
            front_filename,
            front,
            privacy=self.privacy,
        )
        back_path = save_upload(
            self.settings.media_dir,
            session.session_id,
            f"id_back_{scan_id}",
            back_filename,
            back,
            privacy=self.privacy,
        )
        session.id_front, session.id_back = front_path, back_path
        return response

    def _scan_images(
        self, session: Session, front: bytes, back: bytes, client_qr: str | None
    ) -> IdCardResponse:
        # A completed rescan, including a retry response, invalidates prior confirmation.
        # Exceptions roll the request transaction back, preserving the previous card.
        session.id_fields = None
        session.sensitive_id_number = None
        session.sensitive_confirmed_id_number = None
        session.id_number_hmac = None
        session.id_edited = []
        session.id_source = None
        session.id_confirmed = False
        session.id_confirmed_fields = None
        session.id_confirmed_number_hmac = None
        session.results.pop(Module.FACE_MATCH, None)
        if not self.settings.identity_lab_url:
            if self.settings.use_mock_models is not True:
                raise ApiError(503, "identity_unavailable", "Dịch vụ đọc thẻ chưa sẵn sàng.")
            return self.accept_id_card(session, client_qr)
        data = IdentityRuntime(self.settings).scan(front, back)
        codes = data.get("qr_values", [])
        if not isinstance(codes, list) or not all(isinstance(v, str) for v in codes):
            raise ApiError(503, "identity_unavailable", "Dịch vụ đọc thẻ chưa sẵn sàng.")
        candidates = [value for code in codes if (value := parse_cccd_qr(code)) is not None]
        distinct = {value.model_dump_json() for value in candidates}
        if len(distinct) > 1:
            return IdCardResponse(status="retry", retry_hint="QR_INVALID")
        if candidates:
            fields, source = candidates[0], "server_qr"
        else:
            raw = data.get("fields", {})
            if not isinstance(raw, dict):
                raise ApiError(503, "identity_unavailable", "Dịch vụ đọc thẻ chưa sẵn sàng.")
            try:
                fields = IdCardFields(
                    full_name=raw.get("name"),
                    id_number=raw.get("id"),
                    date_of_birth=raw.get("dob"),
                    sex=raw.get("gender") if raw.get("gender") in {"Nam", "Nữ"} else None,
                    address=", ".join(
                        str(raw[k]) for k in ("current_place1", "current_place2") if raw.get(k)
                    )
                    or None,
                )
            except ValueError:
                return IdCardResponse(status="retry", retry_hint="QR_UNREADABLE")
            if not any(fields.model_dump().values()):
                return IdCardResponse(status="retry", retry_hint="QR_UNREADABLE")
            source = "ocr"
        return self._accept_fields(session, fields, source)

    def _accept_fields(self, session: Session, fields: IdCardFields, source: str) -> IdCardResponse:
        session.id_source = source
        session.id_fields = fields.model_dump(mode="json", exclude_none=True, exclude={"id_number"})
        if self.privacy and self.privacy.enabled:
            session.sensitive_id_number = fields.id_number
        session.id_number_hmac = (
            _digest(self._key(), fields.id_number) if fields.id_number else None
        )
        return IdCardResponse(status="ok", fields=fields)

    def accept_id_card(self, session: Session, qr: str | None) -> IdCardResponse:
        if not qr or not qr.strip():
            return IdCardResponse(status="retry", retry_hint="QR_UNREADABLE")
        fields = parse_cccd_qr(qr)
        if fields is None:
            return IdCardResponse(status="retry", retry_hint="QR_INVALID")
        # Số CCCD chỉ giữ dạng HMAC; các trường còn lại giữ để so khi người dùng xác nhận.
        return self._accept_fields(session, fields, "client_qr_mock")

    def confirm_id_card(self, session: Session, confirmed: IdCardFields) -> IdCardConfirmResponse:
        """Người dùng xác nhận (hoặc sửa) thông tin; trường khác QR được ghi chú cho ca duyệt."""
        if session.id_fields is None:
            raise ApiError(409, "id_card_not_received", "Chưa nhận ảnh CCCD.")
        if session.accepted_steps or session.face_scored:
            raise ApiError(
                409, "step_not_allowed", "Hãy bắt đầu lại phiên trước khi đổi thông tin."
            )
        submitted = confirmed.model_dump(mode="json", exclude_unset=True, exclude={"id_number"})
        given = {**session.id_fields, **submitted}
        if self.settings.identity_lab_url and not all(
            (
                confirmed.full_name and confirmed.full_name.strip(),
                confirmed.id_number,
                confirmed.date_of_birth,
                confirmed.sex,
                confirmed.address and confirmed.address.strip(),
            )
        ):
            raise ApiError(422, "identity_incomplete", "Vui lòng điền đủ thông tin trên thẻ.")
        edited = {
            k
            for k in set(given) | set(session.id_fields)
            if session.id_fields.get(k) != given.get(k)
        }
        if (
            confirmed.id_number
            and _digest(self._key(), confirmed.id_number) != session.id_number_hmac
        ):
            edited.add("id_number")
        session.id_edited = sorted(edited)
        session.id_confirmed_fields = given
        session.id_confirmed_number_hmac = (
            _digest(self._key(), confirmed.id_number) if confirmed.id_number else None
        )
        session.id_confirmed = True
        if self.privacy and self.privacy.enabled:
            session.sensitive_confirmed_id_number = (
                confirmed.id_number or session.sensitive_id_number
            )
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
