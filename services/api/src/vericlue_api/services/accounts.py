"""Encrypted account persistence for FLOW-05; no public enrollment route yet.

The caller owns a locked onboarding session and validated face/voice evidence.
Continuity requires its own calibrated protocol. No mock/mixed session can
create an account here; the public enrollment flow is still disabled.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import AccountRow, SessionRow, aware, utcnow
from vericlue_api.services.media_proof import public_key, require_consumed
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import Session
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status
from vericlue_ml.face.continuity import FACE_VOICE_VERSION
from vericlue_ml.face.template import FaceTemplate
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION

ACCOUNT_TTL = timedelta(hours=24)
_GATES = {
    Module.QUALITY,
    Module.CHROMAPULSE,
    Module.CAMPROBE,
    Module.GAZE_TRACKING,
    Module.HEAD_TURN,
    Module.FACE_MATCH,
    Module.VOICE_CHALLENGE,
    Module.LIPSYNC,
}
_PROBABILITIES = {Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.VOICE_SPOOF}


def unavailable() -> ApiError:
    return ApiError(503, "enrollment_unavailable", "Chưa thể hoàn tất ghi danh lúc này.")


def not_eligible() -> ApiError:
    return ApiError(409, "enrollment_not_available", "Phiên chưa thể hoàn tất ghi danh.")


@dataclass(frozen=True)
class AccountReceipt:
    account_id: str
    device_id: str
    expires_at: datetime


@dataclass(frozen=True)
class EnrolledIdentity:
    """Server-internal lookup only; never serialize this as an HTTP response."""

    receipt: AccountReceipt
    template: FaceTemplate = field(repr=False)
    public_key_spki: str = field(repr=False)


class AccountStore:
    """Independent account DEKs survive session deletion, expire after 24 hours."""

    def __init__(self, settings: Settings, db: DBSession) -> None:
        self.settings, self.db = settings, db

    def _master(self) -> bytes:
        try:
            if not self.settings.session_privacy or self.settings.session_master_key is None:
                raise ValueError("Account encryption is mandatory")
            key = base64.b64decode(
                self.settings.session_master_key.get_secret_value(), validate=True
            )
            if len(key) != 32:
                raise ValueError("Invalid master key")
            return key
        except Exception as exc:
            raise unavailable() from exc

    @staticmethod
    def _aad(row: AccountRow, purpose: str) -> bytes:
        # Authenticate lookup metadata as well as the encrypted identity/device/template.
        return json.dumps(
            [
                "vericlue-account-v1",
                row.account_id,
                row.source_session_id,
                row.device_id,
                row.id_number_hmac,
                row.phone_hmac,
                aware(row.created_at).isoformat(),
                aware(row.expires_at).isoformat(),
                purpose,
            ],
            separators=(",", ":"),
        ).encode("ascii")

    @staticmethod
    def _seal(key: bytes, clear: bytes, aad: bytes) -> str:
        nonce = secrets.token_bytes(12)
        return base64.b64encode(b"VCA1" + nonce + AESGCM(key).encrypt(nonce, clear, aad)).decode(
            "ascii"
        )

    @staticmethod
    def _open(key: bytes, sealed: str, aad: bytes) -> bytes:
        raw = base64.b64decode(sealed, validate=True)
        if raw[:4] != b"VCA1" or len(raw) < 32:
            raise ValueError("Invalid encrypted account")
        return AESGCM(key).decrypt(raw[4:16], raw[16:], aad)

    @staticmethod
    def _receipt(row: AccountRow) -> AccountReceipt:
        return AccountReceipt(row.account_id, row.device_id, aware(row.expires_at))

    def _audit(self, row: AccountRow, *, actor: str, action: str) -> None:
        # Account row lock (or uncommitted new row) serializes this independent chain.
        SessionPrivacy(self.settings, self.db).audit(
            "account:" + row.account_id, actor=actor, action=action
        )

    def _eligible(
        self, session: Session, template: FaceTemplate, continuity: ModuleResult | None
    ) -> None:
        s = self.settings
        # Explicitly exclude mock/mixed biometric decisions and development HMAC keys.
        if (
            s.use_mock_models is not False
            or not s.identity_face_from_video
            or not s.identity_consistency_required
            or not s.session_face_checks
            or not s.session_face_models
            or not s.session_voice_models
            or not s.identity_voice_continuity
            or len(s.id_hmac_key.get_secret_value().encode("utf-8")) < 32
        ):
            raise unavailable()
        row = self.db.scalar(
            select(SessionRow).where(SessionRow.session_id == session.session_id).with_for_update()
        )
        if (
            row is None
            or row.status != "pass"
            or row.ever_review
            or row.media_deleted_at is not None
            or session.purpose != "onboarding"
            or not session.completed
            or session.case_id is not None
            or not session.otp_verified
            or not session.phone_hmac
            or not session.id_confirmed
            or session.id_edited
            or session.id_source not in {"server_qr", "ocr"}
            or not session.id_number_hmac
            or session.id_number_hmac != session.id_confirmed_number_hmac
            or not {"media", "signals", "finalize", "voice"}.issubset(session.accepted_steps)
            or session.voice_requested
            or session.voice_owed
            or aware(session.token_expires_at) <= utcnow()
        ):
            raise not_eligible()
        for module in _GATES | _PROBABILITIES:
            result = session.results.get(module)
            if (
                result is None
                or result.status != Status.OK
                or result.error_code is not None
                or "mock" in result.model_version.lower()
                or module in _GATES
                and result.gate != Gate.PASS
                or module in _PROBABILITIES
                and (result.prob_attack is None or not 0 <= result.prob_attack <= 1)
            ):
                raise not_eligible()
        match = session.results[Module.FACE_MATCH]
        if (
            match.model_version != VIDEO_MATCH_VERSION
            or match.quality.get("consistency_verified") is not True
            or template.model_version != VIDEO_MATCH_VERSION
            or template.session_id != session.session_id
            or template.challenge_id != session.challenge.challenge_id
        ):
            raise not_eligible()
        hashes = [e.value for e in match.evidence if e.name == "source_video_sha256"]
        frames = [e.value for e in match.evidence if e.name == "selected_frontal_frame"]
        if (
            hashes != [template.source_video_sha256]
            or len(frames) != 1
            or not isinstance(frames[0], dict)
            or frames[0].get("pixels_sha256") != template.pixels_sha256
        ):
            raise not_eligible()
        # A successful CCCD match cannot substitute for the missing cross-stage check.
        expected = {
            "source_video_sha256": template.source_video_sha256,
            "challenge_id": template.challenge_id,
            "voice_challenge_id": session.voice_challenge_id,
        }
        if (
            continuity is None
            or continuity.module != Module.FACE_CONTINUITY
            or continuity.model_version != FACE_VOICE_VERSION
            or continuity.status != Status.OK
            or continuity.error_code is not None
            or continuity.gate != Gate.PASS
            or any(
                [e.value for e in continuity.evidence if e.name == name] != [value]
                for name, value in expected.items()
            )
        ):
            raise unavailable()
        require_consumed(self.db, session, "face", required=True)
        require_consumed(self.db, session, "voice", required=True)
        public_key(session.media_public_key_spki)

    def create(
        self,
        session: Session,
        template: FaceTemplate,
        *,
        continuity: ModuleResult | None = None,
    ) -> AccountReceipt:
        """Atomic internal enrollment; requires server-owned validated inputs, not HTTP data."""
        master = self._master()
        if continuity is None:
            continuity = session.results.get(Module.FACE_CONTINUITY)
        try:
            # Revalidate even internally copied instances (model_copy skips validators).
            template = FaceTemplate.model_validate_json(template.model_dump_json())
        except Exception as exc:
            raise not_eligible() from exc
        self._eligible(session, template, continuity)
        existing = self.db.scalar(
            select(AccountRow)
            .where(AccountRow.source_session_id == session.session_id)
            .with_for_update()
        )
        if existing is not None:
            # Authenticate existing binding; retries cannot rotate keys or revive expired data.
            identity = self.get(existing.account_id)
            if identity.public_key_spki != session.media_public_key_spki:
                raise not_eligible()
            return identity.receipt
        self.expire()
        now = utcnow()
        row = AccountRow(
            account_id="acct_" + secrets.token_hex(16),
            source_session_id=session.session_id,
            id_number_hmac=session.id_number_hmac,
            phone_hmac=session.phone_hmac,
            device_id="dev_" + secrets.token_hex(16),
            created_at=now,
            expires_at=now + ACCOUNT_TTL,
        )
        dek = AESGCM.generate_key(bit_length=256)
        row.wrapped_key = self._seal(master, dek, self._aad(row, "dek"))
        payload = {
            "template": template.model_dump(mode="json"),
            "public_key_spki": session.media_public_key_spki,
            "key_fingerprint": hashlib.sha256(
                base64.b64decode(session.media_public_key_spki, validate=True)
            ).hexdigest(),
        }
        row.encrypted_payload = self._seal(
            dek,
            json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8"),
            self._aad(row, "identity"),
        )
        try:
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
        except IntegrityError as exc:
            # Same neutral response for duplicate identities and concurrent enrollment.
            raise not_eligible() from exc
        self._audit(row, actor="system-enrollment", action="account_created")
        return self._receipt(row)

    def get(self, account_id: str) -> EnrolledIdentity:
        """Private lookup, fail closed at TTL even if the cleanup worker is delayed."""
        row = self.db.scalar(
            select(AccountRow).where(AccountRow.account_id == account_id).with_for_update()
        )
        if (
            row is None
            or row.destroyed_at is not None
            or aware(row.expires_at) <= utcnow()
            or row.wrapped_key is None
            or row.encrypted_payload is None
        ):
            raise ApiError(410, "account_unavailable", "Không thể dùng tài khoản này lúc này.")
        try:
            dek = self._open(self._master(), row.wrapped_key, self._aad(row, "dek"))
            payload = json.loads(self._open(dek, row.encrypted_payload, self._aad(row, "identity")))
            template = FaceTemplate.model_validate_json(json.dumps(payload["template"]))
            spki = payload["public_key_spki"]
            public_key(spki)
            if (
                template.session_id != row.source_session_id
                or template.model_version != VIDEO_MATCH_VERSION
                or payload["key_fingerprint"]
                != hashlib.sha256(base64.b64decode(spki, validate=True)).hexdigest()
            ):
                raise ValueError("Account binding mismatch")
            identity = EnrolledIdentity(self._receipt(row), template, spki)
        except Exception as exc:
            raise unavailable() from exc
        self._audit(row, actor="system-identity", action="template_read")
        return identity

    def expire(self, *, now: datetime | None = None) -> int:
        """Destroy independent account DEKs and sensitive payloads; keep opaque tombstones."""
        now = aware(now or utcnow())
        rows = self.db.scalars(
            select(AccountRow)
            .where(AccountRow.destroyed_at.is_(None), AccountRow.expires_at <= now)
            .order_by(AccountRow.account_id)
            .with_for_update(skip_locked=True)
        )
        count = 0
        for row in rows:
            row.wrapped_key = row.encrypted_payload = None
            row.id_number_hmac = row.phone_hmac = None
            row.destroyed_at = now
            self._audit(row, actor="system-cleanup", action="account_key_destroyed")
            count += 1
        self.db.flush()
        return count
