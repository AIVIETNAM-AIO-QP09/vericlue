"""Token HMAC theo phiên; không chứa dữ liệu định danh người dân."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime


def token_digest(token: str) -> str:
    """Băm token để lưu trong DB thay cho thông tin xác thực gốc."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class SessionTokenSigner:
    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("Khóa ký phiên phải có ít nhất 32 byte.")
        self._key = key

    def issue(self, session_id: str, expires_at: datetime) -> str:
        """Cấp token có hạn, ràng buộc vào đúng một phiên."""
        payload = _encode(
            json.dumps(
                {
                    "sid": session_id,
                    "exp": expires_at.timestamp(),
                    "nonce": secrets.token_hex(16),
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        signature = _encode(hmac.digest(self._key, payload.encode("ascii"), "sha256"))
        return f"{payload}.{signature}"

    def verify(self, token: str, session_id: str, *, now: datetime | None = None) -> bool:
        """Từ chối token sai chữ ký, sai phiên, quá hạn hoặc sai định dạng."""
        if len(token) > 2048 or not token.isascii():
            return False
        try:
            payload, signature = token.split(".")
            expected = _encode(hmac.digest(self._key, payload.encode("ascii"), "sha256"))
            if not hmac.compare_digest(signature, expected):
                return False
            claims = json.loads(
                base64.b64decode(
                    payload + "=" * (-len(payload) % 4),
                    altchars=b"-_",
                    validate=True,
                )
            )
            expiry = claims["exp"]
            return (
                claims["sid"] == session_id
                and type(expiry) in {int, float}
                and expiry > (now or datetime.now(UTC)).timestamp()
            )
        except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError):
            return False
