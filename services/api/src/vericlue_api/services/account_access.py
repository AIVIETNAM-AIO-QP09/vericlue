"""Revocable dashboard login; never turns a password into an eKYC verdict."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import (
    AccountAccessAttemptRow,
    AccountAccessCredentialRow,
    AccountAccessFaceUseRow,
    AccountAccessTokenRow,
    AccountRow,
    DecisionRow,
    SessionRow,
    aware,
    utcnow,
)
from vericlue_api.schemas.account_access import (
    AccountAccessSession,
    AccountAccessSetupRequest,
    AccountPasswordRequest,
    AccountProfile,
)
from vericlue_api.services.account_auth import AccountAuth
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.media_proof import require_consumed
from vericlue_api.services.session_store import Session
from vericlue_ml.common.result import Gate, Module, Status
from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DBSession

    from vericlue_api.core.state import AppState

ACCESS_TTL = timedelta(minutes=15)
ATTEMPT_WINDOW = timedelta(minutes=5)
PASSWORD_ITERATIONS = 600_000
POLICY_VERSION = "account-profile-v1"


def access_denied() -> ApiError:
    return ApiError(401, "account_login_failed", "Tên đăng nhập hoặc mật khẩu chưa đúng.")


def access_expired() -> ApiError:
    return ApiError(
        401, "account_access_expired", "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
    )


@dataclass(frozen=True)
class LoginRejected:
    """Return through the router, so failed-attempt counters commit instead of rolling back."""

    error: ApiError


def erase_account_access(db: DBSession, account_id: str) -> None:
    """Destroy access DEK and lookup, revoke sessions with the account's existing lifecycle."""
    row = db.get(AccountAccessCredentialRow, account_id)
    if row is not None:
        row.wrapped_key = row.encrypted_payload = row.username_hmac = None
    db.execute(
        update(AccountAccessTokenRow)
        .where(
            AccountAccessTokenRow.account_id == account_id,
            AccountAccessTokenRow.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def _verifier(password: str) -> dict:
    salt = secrets.token_bytes(16)
    return {
        "algorithm": "pbkdf2-sha256",
        "iterations": PASSWORD_ITERATIONS,
        "salt": salt.hex(),
        "digest": _password_hash(password, salt).hex(),
    }


def _password_matches(password: str, verifier: dict) -> bool:
    if (
        verifier.get("algorithm") != "pbkdf2-sha256"
        or verifier.get("iterations") != PASSWORD_ITERATIONS
    ):
        raise ValueError("Unsupported password verifier")
    salt, digest = bytes.fromhex(verifier["salt"]), bytes.fromhex(verifier["digest"])
    if len(salt) != 16 or len(digest) != 32:
        raise ValueError("Invalid password verifier")
    return hmac.compare_digest(_password_hash(password, salt), digest)


class AccountAccess:
    def __init__(self, state: AppState):
        self.state, self.db, self.accounts, self.settings = (
            state,
            state.db,
            state.accounts,
            state.settings,
        )

    def _enabled(self) -> None:
        if (
            not self.settings.account_access_enabled
            or not self.settings.account_enrollment
            or not self.settings.session_privacy
            or self.settings.product_mode != "ekyc"
            or self.settings.use_mock_models is not False
            and not self.settings.manual_full_demo
            or len(self.settings.id_hmac_key.get_secret_value()) < 32
        ):
            raise ApiError(503, "account_access_unavailable", "Đăng nhập tài khoản chưa sẵn sàng.")

    def _digest(self, purpose: str, value: str) -> str:
        return hmac.new(
            self.settings.id_hmac_key.get_secret_value().encode(),
            f"account-access-v1:{purpose}:{value}".encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _aad(row: AccountAccessCredentialRow, purpose: str) -> bytes:
        return json.dumps(
            [
                "vericlue-account-access-v1",
                row.account_id,
                aware(row.expires_at).isoformat(),
                purpose,
            ],
            separators=(",", ":"),
        ).encode("ascii")

    def _open(self, row: AccountAccessCredentialRow) -> dict:
        if not row.wrapped_key or not row.encrypted_payload or aware(row.expires_at) <= utcnow():
            raise access_expired()
        key = AccountStore._open(self.accounts._master(), row.wrapped_key, self._aad(row, "dek"))
        payload = json.loads(
            AccountStore._open(key, row.encrypted_payload, self._aad(row, "profile"))
        )
        profile = AccountProfile.model_validate(payload["profile"])
        if (
            profile.account_id != row.account_id
            or profile.expires_at != aware(row.expires_at)
            or self._digest("username", profile.username) != row.username_hmac
            or payload.get("device_id") != row.device_id
            or payload.get("policy_version") != row.policy_version
            or row.policy_version != POLICY_VERSION
        ):
            raise access_expired()
        return payload

    def _current(self, row: AccountAccessCredentialRow) -> tuple[AccountProfile, dict]:
        identity = self.accounts.get(row.account_id)
        # Match enrollment/recovery/cleanup lock order: account -> credential -> token.
        # Refresh after the account lock so an earlier read cannot survive recovery.
        self.db.refresh(row, with_for_update=True)
        payload = self._open(row)
        profile = AccountProfile.model_validate(payload["profile"])
        mode = "manual_full_demo" if self.settings.manual_full_demo else "standard"
        policy = self.settings.manual_demo_policy
        if (
            row.device_id != identity.receipt.device_id
            or profile.evaluation_mode != mode
            or profile.demo_policy_id
            != (policy.policy_id if self.settings.manual_full_demo and policy else None)
            or profile.expires_at != identity.receipt.expires_at
        ):
            raise access_expired()
        return profile, payload

    def _passed_identity(self, session: Session):
        self._enabled()
        self.state.flow._ensure_evaluation_binding(session)
        row = self.db.get(SessionRow, session.session_id)
        decision = self.db.scalar(
            select(DecisionRow)
            .where(
                DecisionRow.session_id == session.session_id,
            )
            .order_by(DecisionRow.id.desc())
            .limit(1)
        )
        if (
            not session.completed
            or session.case_id is not None
            or session.voice_owed
            or session.voice_requested
            or aware(session.token_expires_at) <= utcnow()
            or row is None
            or row.status != "pass"
            or row.ever_review
            or row.media_deleted_at is not None
            or row.decided_at is None
            or decision is None
            or decision.action != "pass"
            or session.created_model_mode not in {"real", "manual_full_demo"}
        ):
            raise ApiError(
                409, "account_verification_required", "Vui lòng hoàn tất xác minh tài khoản."
            )
        if session.purpose == "reauth":
            self._reauth_evidence(session)
            return AccountAuth(self.accounts).current(session)
        if session.purpose not in {"onboarding", "recovery"}:
            raise access_expired()
        receipt = self.accounts.receipt_for_session(session)
        return self.accounts.get(receipt.account_id)

    def _reauth_evidence(self, session: Session) -> None:
        AccountAuth(self.accounts).require_verified(session)
        require_consumed(self.db, session, "face", required=True)
        if not {"media", "signals", "finalize"}.issubset(session.accepted_steps):
            raise access_expired()
        gates = {Module.QUALITY, Module.CAMPROBE, Module.FACE_MATCH}
        attack = {Module.FACE_PAD, Module.FACE_DEEPFAKE}
        if not self.settings.manual_full_demo:
            gates.add(Module.CHROMAPULSE)
        asked_voice = (
            self.db.scalar(
                select(DecisionRow.id)
                .where(
                    DecisionRow.session_id == session.session_id,
                    DecisionRow.action == "voice_challenge",
                )
                .limit(1)
            )
            is not None
        )
        if (
            asked_voice
            or session.voice_challenge_id is not None
            or "voice" in session.accepted_steps
        ):
            if "voice" not in session.accepted_steps:
                raise access_expired()
            require_consumed(self.db, session, "voice", required=True)
            gates |= {Module.VOICE_CHALLENGE, Module.LIPSYNC}
            attack.add(Module.VOICE_SPOOF)
        policy = self.settings.manual_demo_policy
        suffix = policy.version_suffix if self.settings.manual_full_demo and policy else ""
        for module in gates | attack:
            result = session.results.get(module)
            if (
                result is None
                or result.status != Status.OK
                or result.error_code is not None
                or "mock" in result.model_version.lower()
                or module in gates
                and result.gate != Gate.PASS
                or module in attack
                and result.gate == Gate.FAIL
                or not self.settings.manual_full_demo
                and module in attack
                and (result.prob_attack is None or not 0 <= result.prob_attack <= 1)
                or not self.settings.manual_full_demo
                and result.quality.get("manual_demo") is True
            ):
                raise access_expired()
            if (
                self.settings.manual_full_demo
                and module == Module.VOICE_CHALLENGE
                and (
                    not self.settings.voice_content_pin_matches(
                        session.created_voice_content_version
                    )
                    or result.model_version != self.settings.voice_content_model_version
                )
            ):
                raise access_expired()
            if self.settings.manual_full_demo and module in {Module.VOICE_SPOOF, Module.LIPSYNC}:
                accepts = (
                    policy.accepts_voice_spoof
                    if module == Module.VOICE_SPOOF
                    else policy.accepts_lipsync
                )
                if not accepts(result):
                    raise access_expired()
            if (
                self.settings.manual_full_demo
                and module in attack | {Module.LIPSYNC}
                and (
                    result.gate != Gate.PASS
                    or not suffix
                    or not result.model_version.endswith(suffix)
                    or result.quality.get("manual_demo") is not True
                    or result.quality.get("demo_policy_id") != policy.policy_id
                )
            ):
                raise access_expired()
        match = session.results[Module.FACE_MATCH]
        if (
            match.model_version != REAUTH_MATCH_VERSION + suffix
            or match.quality.get("enrolled_reference") is not True
            or [e.value for e in match.evidence if e.name == "reference_account_id"]
            != [session.account_id]
            or self.settings.manual_full_demo
            and (
                match.quality.get("manual_demo") is not True
                or match.quality.get("demo_policy_id") != policy.policy_id
            )
        ):
            raise access_expired()

    def setup(self, session: Session, request: AccountAccessSetupRequest) -> AccountProfile:
        identity = self._passed_identity(session)
        account = self.db.get(AccountRow, identity.receipt.account_id)
        self.accounts.expire()
        existing = self.db.get(AccountAccessCredentialRow, account.account_id)
        previous = self._open(existing) if existing and existing.encrypted_payload else None
        password = request.password.get_secret_value()
        if existing and existing.setup_session_id == session.session_id:
            if (
                previous
                and previous["profile"]["username"] == request.username
                and _password_matches(password, previous["password"])
            ):
                return AccountProfile.model_validate(previous["profile"])
            raise ApiError(409, "account_setup_conflict", "Lượt thiết lập này đã được sử dụng.")
        if previous is not None and session.purpose != "recovery":
            raise ApiError(
                409, "account_already_configured", "Tài khoản đã có thông tin đăng nhập."
            )
        username_hmac = self._digest("username", request.username)
        owner = self.db.scalar(
            select(AccountAccessCredentialRow).where(
                AccountAccessCredentialRow.username_hmac == username_hmac,
            )
        )
        if owner is not None and owner.account_id != account.account_id:
            raise ApiError(409, "username_unavailable", "Tên đăng nhập này chưa thể sử dụng.")
        fields = session.id_confirmed_fields or session.id_fields or {}
        full_name = fields.get("full_name")
        full_name = (
            full_name.strip()[:200] if isinstance(full_name, str) and full_name.strip() else None
        )
        id_number = session.sensitive_confirmed_id_number or session.sensitive_id_number
        masked = (
            "********" + id_number[-4:]
            if isinstance(id_number, str) and re.fullmatch(r"[0-9]{12}", id_number)
            else None
        )
        if previous:
            full_name = full_name or previous["profile"]["full_name"]
            masked = masked or previous["profile"]["masked_id_number"]
        policy = self.settings.manual_demo_policy
        profile = AccountProfile(
            account_id=account.account_id,
            username=request.username,
            full_name=full_name,
            masked_id_number=masked,
            created_at=aware(account.created_at),
            expires_at=aware(account.expires_at),
            evaluation_mode="manual_full_demo" if self.settings.manual_full_demo else "standard",
            demo_policy_id=policy.policy_id if self.settings.manual_full_demo and policy else None,
        )
        row = existing or AccountAccessCredentialRow(account_id=account.account_id)
        payload = {
            "profile": profile.model_dump(mode="json"),
            "password": _verifier(password),
            "device_id": identity.receipt.device_id,
            "policy_version": POLICY_VERSION,
        }
        try:
            with self.db.begin_nested():
                row.username_hmac = username_hmac
                row.device_id = identity.receipt.device_id
                row.setup_session_id = session.session_id
                row.policy_version = POLICY_VERSION
                row.consented_at = utcnow()
                row.expires_at = aware(account.expires_at)
                key = AESGCM.generate_key(bit_length=256)
                row.wrapped_key = AccountStore._seal(
                    self.accounts._master(), key, self._aad(row, "dek")
                )
                row.encrypted_payload = AccountStore._seal(
                    key, json.dumps(payload, ensure_ascii=False).encode(), self._aad(row, "profile")
                )
                self.db.add(row)
                self.db.flush()
        except IntegrityError as exc:
            raise ApiError(
                409, "username_unavailable", "Tên đăng nhập này chưa thể sử dụng."
            ) from exc
        self.db.execute(
            update(AccountAccessTokenRow)
            .where(
                AccountAccessTokenRow.account_id == account.account_id,
                AccountAccessTokenRow.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )
        self.accounts._audit(
            account, actor="account-holder", action="profile_consent_password_setup"
        )
        return profile

    def _attempt(self, kind: str, value: str, limit: int) -> bool:
        now = utcnow()
        digest = self._digest(kind, value)
        row = self.db.scalar(
            select(AccountAccessAttemptRow)
            .where(
                AccountAccessAttemptRow.bucket_hash == digest,
            )
            .with_for_update()
        )
        if row is None:
            try:
                with self.db.begin_nested():
                    row = AccountAccessAttemptRow(
                        bucket_hash=digest, window_started_at=now, attempts=0
                    )
                    self.db.add(row)
                    self.db.flush()
            except IntegrityError:
                row = self.db.scalar(
                    select(AccountAccessAttemptRow)
                    .where(
                        AccountAccessAttemptRow.bucket_hash == digest,
                    )
                    .with_for_update()
                )
        if aware(row.window_started_at) + ATTEMPT_WINDOW <= now:
            row.window_started_at, row.attempts = now, 0
        if row.attempts >= limit:
            return False
        row.attempts += 1
        return True

    def password(
        self, request: AccountPasswordRequest, peer: str
    ) -> AccountAccessSession | LoginRejected:
        self._enabled()
        if not peer or not self._attempt("peer", peer, 20):
            return LoginRejected(
                ApiError(429, "account_login_limited", "Vui lòng đợi 5 phút rồi thử đăng nhập lại.")
            )
        # Remove old IP buckets; no raw address, username or password enters this table.
        self.db.execute(
            delete(AccountAccessAttemptRow).where(
                AccountAccessAttemptRow.window_started_at < utcnow() - timedelta(hours=1),
            )
        )
        row = self.db.scalar(
            select(AccountAccessCredentialRow).where(
                AccountAccessCredentialRow.username_hmac
                == self._digest("username", request.username),
            )
        )
        password = request.password.get_secret_value()
        if row is None:
            _password_hash(password, bytes(16))
            return LoginRejected(access_denied())
        if not self._attempt("account", row.account_id, 5):
            _password_hash(password, bytes(16))
            return LoginRejected(access_denied())
        try:
            profile, payload = self._current(row)
            matches = (
                _password_matches(password, payload["password"])
                and profile.username == request.username
            )
        except Exception:
            _password_hash(password, bytes(16))
            return LoginRejected(access_denied())
        if not matches:
            return LoginRejected(access_denied())
        bucket = self.db.get(AccountAccessAttemptRow, self._digest("account", row.account_id))
        bucket.attempts = 0
        return self._issue(row, profile, "password")

    def _issue(
        self, row: AccountAccessCredentialRow, profile: AccountProfile, method: str
    ) -> AccountAccessSession:
        now = utcnow()
        token = "vca_" + secrets.token_urlsafe(32)
        expires_at = min(now + ACCESS_TTL, profile.expires_at)
        self.db.add(
            AccountAccessTokenRow(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                account_id=row.account_id,
                device_id=row.device_id,
                authentication_method=method,
                created_at=now,
                expires_at=expires_at,
            )
        )
        self.db.execute(
            delete(AccountAccessTokenRow).where(AccountAccessTokenRow.expires_at <= now)
        )
        return AccountAccessSession(
            access_token=token, expires_at=expires_at, authentication_method=method, profile=profile
        )

    def face(self, session: Session) -> AccountAccessSession:
        if session.purpose != "reauth":
            raise access_expired()
        identity = self._passed_identity(session)
        row = self.db.get(AccountAccessCredentialRow, identity.receipt.account_id)
        if row is None or row.encrypted_payload is None:
            raise ApiError(
                409, "account_setup_required", "Vui lòng thiết lập tên đăng nhập và mật khẩu."
            )
        profile, _ = self._current(row)
        try:
            with self.db.begin_nested():
                self.db.add(
                    AccountAccessFaceUseRow(
                        session_id=session.session_id, account_id=row.account_id
                    )
                )
                self.db.flush()
        except IntegrityError as exc:
            raise ApiError(
                409,
                "account_face_session_used",
                "Lượt xác minh đã được sử dụng. Vui lòng đăng nhập lại.",
            ) from exc
        return self._issue(row, profile, "face")

    def current(self, token: str) -> tuple[AccountAccessTokenRow, AccountProfile]:
        self._enabled()
        if not re.fullmatch(r"vca_[A-Za-z0-9_-]{43}", token):
            raise access_expired()
        row = self.db.scalar(
            select(AccountAccessTokenRow).where(
                AccountAccessTokenRow.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            )
        )
        if row is None or row.revoked_at is not None or aware(row.expires_at) <= utcnow():
            raise access_expired()
        credential = self.db.get(AccountAccessCredentialRow, row.account_id)
        if credential is None or credential.device_id != row.device_id:
            raise access_expired()
        try:
            profile, _ = self._current(credential)
            self.db.refresh(row, with_for_update=True)
        except Exception as exc:
            raise access_expired() from exc
        if row.revoked_at is not None or aware(row.expires_at) <= utcnow():
            raise access_expired()
        if credential.device_id != row.device_id:
            raise access_expired()
        return row, profile

    def logout(self, token: str) -> None:
        row, _ = self.current(token)
        row.revoked_at = utcnow()
