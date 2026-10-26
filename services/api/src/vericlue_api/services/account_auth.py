"""Registered-key proof, independent of biometric acceptance and camera attestation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.exc import IntegrityError

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import DeviceProofUseRow, aware, utcnow
from vericlue_api.schemas.session import DeviceChallenge
from vericlue_api.services.accounts import AccountStore, EnrolledIdentity
from vericlue_api.services.media_proof import bind_key, public_key
from vericlue_api.services.session_store import Session


def rejected() -> ApiError:
    return ApiError(409, "recovery_required", "Vui lòng thực hiện khôi phục tài khoản.")


def message(session: Session) -> bytes:
    """Canonical bytes supplied directly to Android; the client signs without re-encoding."""
    if (
        session.purpose != "reauth"
        or not session.account_id
        or not session.registered_device_id
        or not session.device_auth_nonce
        or session.device_auth_expires_ms is None
    ):
        raise rejected()
    return json.dumps(
        {
            "version": "vericlue-device-auth-v1",
            "session_id": session.session_id,
            "account_id": session.account_id,
            "device_id": session.registered_device_id,
            "purpose": session.purpose,
            "nonce": session.nonce,
            "server_nonce": session.device_auth_nonce,
            "expires_at_ms": session.device_auth_expires_ms,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


class AccountAuth:
    def __init__(self, accounts: AccountStore) -> None:
        self.accounts = accounts
        self.db = accounts.db

    def current(self, session: Session) -> EnrolledIdentity:
        """Re-check every protected operation, including already L0-verified sessions."""
        if not session.account_id or session.purpose not in {"reauth", "recovery"}:
            raise rejected()
        identity = self.accounts.get(session.account_id)
        if identity.receipt.device_id != session.registered_device_id:
            raise rejected()
        if (
            session.purpose == "reauth"
            and identity.public_key_spki != session.media_public_key_spki
        ):
            raise rejected()
        return identity

    def bind(
        self, session: Session, account_id: str, device_id: str | None
    ) -> DeviceChallenge | None:
        identity = self.accounts.get(account_id)
        if session.purpose == "reauth" and device_id != identity.receipt.device_id:
            raise rejected()
        session.account_id = account_id
        session.registered_device_id = identity.receipt.device_id
        if session.purpose == "recovery":
            return None
        bind_key(session, identity.public_key_spki)
        now_ms = int(utcnow().timestamp() * 1000)
        session.device_auth_nonce = secrets.token_hex(32)
        session.device_auth_expires_ms = min(
            now_ms + 60_000,
            int(session.token_expires_at.timestamp() * 1000),
            int(identity.receipt.expires_at.timestamp() * 1000),
        )
        return DeviceChallenge(
            message=base64.b64encode(message(session)).decode("ascii"),
            expires_at=datetime.fromtimestamp(session.device_auth_expires_ms / 1000, UTC),
        )

    def verify(self, session: Session, signature: str) -> None:
        identity = self.current(session)
        payload = message(session)
        if (
            session.completed
            or session.device_verified
            or session.accepted_steps
            or int(utcnow().timestamp() * 1000) >= session.device_auth_expires_ms
            or utcnow() >= aware(session.token_expires_at)
        ):
            raise rejected()
        try:
            raw = base64.b64decode(signature, validate=True)
            if not 8 <= len(raw) <= 80 or base64.b64encode(raw).decode("ascii") != signature:
                raise ValueError("Signature format")
            public_key(identity.public_key_spki).verify(raw, payload, ec.ECDSA(hashes.SHA256()))
        except Exception as exc:
            raise rejected() from exc
        try:
            with self.db.begin_nested():
                self.db.add(
                    DeviceProofUseRow(
                        session_id=session.session_id,
                        message_sha256=hashlib.sha256(payload).hexdigest(),
                    )
                )
                self.db.flush()
        except IntegrityError as exc:
            raise rejected() from exc
        session.device_verified = True

    def require_verified(self, session: Session) -> None:
        self.current(session)
        claim = self.db.get(DeviceProofUseRow, session.session_id)
        if (
            not session.device_verified
            or claim is None
            or claim.message_sha256 != hashlib.sha256(message(session)).hexdigest()
        ):
            raise rejected()

    def check_phone(self, session: Session, phone: str) -> None:
        self.current(session)
        expected = self.accounts.phone_hmac(session.account_id)
        actual = hmac.new(
            self.accounts.settings.id_hmac_key.get_secret_value().encode(),
            phone.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not expected or not hmac.compare_digest(expected, actual):
            raise rejected()
