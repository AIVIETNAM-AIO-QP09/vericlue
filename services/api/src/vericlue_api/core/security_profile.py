"""Fail-closed configuration checks; do not start DB/model/crypto workers here."""

from __future__ import annotations

import base64
import binascii
from typing import TYPE_CHECKING

from vericlue_api.core.errors import ApiError

if TYPE_CHECKING:
    from vericlue_api.core.config import Settings

_PLACEHOLDERS = (b"dev-only", b"change-me", b"changeme", b"replace-me", b"your-secret")


def _text_secret(value) -> bytes:
    return value.get_secret_value().encode("utf-8") if value is not None else b""


def _usable_secret(value: bytes) -> bool:
    # Entropy comes from the operator's CSPRNG; syntax checks cannot prove it.
    return len(value) >= 32 and len(set(value)) > 1 and not value.lower().startswith(_PLACEHOLDERS)


def security_profile_checks(settings: Settings) -> dict[str, bool]:
    """Return only named booleans, never values, hashes, paths or credentials."""
    master_text = _text_secret(settings.session_master_key)
    try:
        master = base64.b64decode(master_text, validate=True)
        master_valid = len(master) == 32 and base64.b64encode(master) == master_text
    except (ValueError, binascii.Error):
        master, master_valid = b"", False
    hmac_key = _text_secret(settings.id_hmac_key)
    token_key = _text_secret(settings.session_signing_secret)
    distinct = (
        bool(master and hmac_key and token_key)
        and len({master, hmac_key, token_key}) == 3
        and master_text not in {hmac_key, token_key}
    )
    return {
        "ekyc_product_mode": settings.product_mode == "ekyc",
        "privacy_consent": settings.require_privacy_consent,
        "session_privacy": settings.session_privacy,
        "signed_media": settings.require_media_proof,
        "master_key": master_valid and _usable_secret(master),
        "identity_hmac_key": _usable_secret(hmac_key),
        "session_signing_key": _usable_secret(token_key),
        "independent_secrets": distinct,
        "real_model_mode": settings.use_mock_models is False,
    }


def validate_security_profile(settings: Settings) -> None:
    """Reject an incomplete protected profile before accepting any request."""
    if settings.security_profile != "protected":
        return
    if not all(security_profile_checks(settings).values()):
        raise ApiError(
            503,
            "security_profile_unavailable",
            "Cấu hình bảo vệ dữ liệu chưa sẵn sàng. Vui lòng kiểm tra cấu hình máy chủ.",
        )


def ensure_otp_available(settings: Settings) -> None:
    """The implemented SMS channel is simulated and can only run in synthetic mocks."""
    if settings.security_profile != "synthetic" or settings.use_mock_models is not True:
        raise ApiError(
            503,
            "otp_unavailable",
            "Chức năng xác minh số điện thoại chưa sẵn sàng. Vui lòng thử lại sau.",
        )
