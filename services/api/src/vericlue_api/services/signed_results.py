"""Issue short-lived integration assertions from committed server decisions only."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import DecisionRow, SessionRow, aware, utcnow
from vericlue_api.schemas.result import ResultClaims, SignedResult
from vericlue_api.services.account_auth import AccountAuth
from vericlue_api.services.accounts import AccountReceipt, AccountStore
from vericlue_api.services.media_proof import require_consumed
from vericlue_api.services.session_store import Session
from vericlue_ml.common.result import Gate, Module, Status


def unavailable() -> ApiError:
    return ApiError(409, "result_not_available", "Chưa có kết quả phù hợp cho phiên này.")


class SignedResultService:
    def __init__(self, settings: Settings, db: DBSession, accounts: AccountStore) -> None:
        self.settings, self.db, self.accounts = settings, db, accounts

    def _reauth_pass(self, session: Session) -> AccountReceipt:
        auth = AccountAuth(self.accounts)
        auth.require_verified(session)
        require_consumed(self.db, session, "face", required=True)
        from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION

        required_gates = {Module.QUALITY, Module.CAMPROBE, Module.CHROMAPULSE, Module.FACE_MATCH}
        probabilities = {Module.FACE_PAD, Module.FACE_DEEPFAKE}
        if session.voice_challenge_id is not None or "voice" in session.accepted_steps:
            required_gates |= {Module.VOICE_CHALLENGE, Module.LIPSYNC}
            probabilities.add(Module.VOICE_SPOOF)
            require_consumed(self.db, session, "voice", required=True)
            if "voice" not in session.accepted_steps:
                raise unavailable()
        if (
            not self.settings.session_face_models
            or not {"media", "signals", "finalize"}.issubset(session.accepted_steps)
            or session.voice_requested
            or session.voice_owed
        ):
            raise unavailable()
        for module in required_gates | probabilities:
            result = session.results.get(module)
            if (
                result is None
                or result.status != Status.OK
                or result.error_code is not None
                or module in required_gates
                and result.gate != Gate.PASS
                or module in probabilities
                and result.prob_attack is None
            ):
                raise unavailable()
        match = session.results[Module.FACE_MATCH]
        if (
            match.model_version != REAUTH_MATCH_VERSION
            or match.quality.get("enrolled_reference") is not True
            or [e.value for e in match.evidence if e.name == "reference_account_id"]
            != [session.account_id]
        ):
            raise unavailable()
        return auth.current(session).receipt

    def issue(self, session: Session) -> SignedResult:
        signer = self.settings.result_signer
        # Never certify a mock/mixed run, a saved mock session after a mode change,
        # a staff override, L0 acknowledgement, intermediate result or legacy session.
        if (
            self.settings.use_mock_models is not False
            or session.created_model_mode != "real"
            or not session.result_issuer
            or not session.result_audience
            or session.result_issuer != self.settings.result_issuer
            or session.result_audience != self.settings.result_audience
            or not self.settings.session_privacy
            or session.purpose not in {"reauth", "recovery"}
            or not session.nonce
            or not session.completed
            or session.case_id is not None
            or not session.results
            or any("mock" in r.model_version.lower() for r in session.results.values())
        ):
            raise unavailable()
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
            row is None
            or row.status not in {"pass", "deny", "recovery_required"}
            or row.ever_review
            or row.media_deleted_at is not None
            or row.decided_at is None
            or decision is None
            or decision.action != row.status
        ):
            raise unavailable()
        issued_at = int(aware(decision.created_at).timestamp())
        expiry = min(
            issued_at + self.settings.result_ttl_seconds,
            int(aware(session.token_expires_at).timestamp()),
        )
        receipt = None
        if row.status == "pass":
            if session.purpose == "recovery":
                self.accounts.validate_recovery(session)
                receipt = self.accounts.receipt_for_session(session)
            else:
                receipt = self._reauth_pass(session)
            expiry = min(expiry, int(receipt.expires_at.timestamp()))
        elif session.purpose != "reauth":
            raise unavailable()
        elif session.account_id:
            bound = AccountAuth(self.accounts).current(session).receipt
            expiry = min(expiry, int(bound.expires_at.timestamp()))
        now = int(utcnow().timestamp())
        if not issued_at <= now < expiry:
            raise unavailable()
        claims = ResultClaims(
            version=1,
            issuer=self.settings.result_issuer,
            audience=self.settings.result_audience,
            result_id="res_"
            + hashlib.sha256(
                f"vericlue-result-v1:{session.session_id}:{decision.id}".encode("ascii")
            ).hexdigest(),
            session_id=session.session_id,
            purpose=session.purpose,
            nonce=session.nonce,
            status=row.status,
            issued_at=issued_at,
            expires_at=expiry,
            account_id=receipt.account_id if receipt else None,
            device_id=receipt.device_id if receipt else None,
        )
        return signer.issue(claims)
