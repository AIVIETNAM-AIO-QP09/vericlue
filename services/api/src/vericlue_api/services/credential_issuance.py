"""Issue from committed, real server pass decisions plus the current device's consent signature."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.exc import IntegrityError

from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import decode
from vericlue_api.core.state import AppState
from vericlue_api.db.models import CredentialIssuanceRow, aware, utcnow
from vericlue_api.schemas.credential import (
    CredentialAuthorization,
    CredentialIssueRequest,
    CredentialKey,
    CredentialOfferRequest,
    VerificationClaims,
    VerificationCredential,
)
from vericlue_api.schemas.result import ResultClaims
from vericlue_api.services.accounts import EnrolledIdentity
from vericlue_api.services.credential_worker import CredentialWorker
from vericlue_api.services.media_proof import public_key
from vericlue_api.services.session_store import Session


def rejected() -> ApiError:
    return ApiError(409, "credential_not_available", "Chưa có chứng nhận phù hợp cho phiên này.")


class CredentialIssuance:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.worker = CredentialWorker(state.settings)

    def _context(
        self, session: Session, offer: CredentialOfferRequest
    ) -> tuple[VerificationClaims, EnrolledIdentity, CredentialKey, str, bytes]:
        if not self.state.settings.private_credentials:
            from vericlue_api.services.credential_worker import unavailable

            raise unavailable()
        # Internal output only, never an assertion/verdict supplied by the HTTP client.
        envelope = self.state.signed_results.issue(session)
        source = ResultClaims.model_validate_json(decode(envelope.payload))
        if source.status != "pass":
            raise rejected()
        identity = self.state.accounts.get(source.account_id)
        if identity.receipt.device_id != source.device_id:
            raise rejected()
        issued = source.issued_at // 10 * 10
        expiry = source.expires_at // 10 * 10
        if not issued <= int(utcnow().timestamp()) < expiry:
            raise rejected()
        key = self.worker.public_key()
        offer_hash = hashlib.sha256(decode(offer.commitment)).hexdigest()
        claims = VerificationClaims(
            issuer=source.issuer,
            valid_from=issued,
            valid_until=expiry,
            source_result_id=source.result_id,
            account_id=source.account_id,
            device_id=source.device_id,
            source_purpose=source.purpose,
        )
        message = json.dumps(
            {
                "protocol": "vericlue-credential-authorization-v1",
                "session_id": session.session_id,
                "source_result_id": source.result_id,
                "account_id": source.account_id,
                "device_id": source.device_id,
                "offer_sha256": offer_hash,
                "key_id": key.key_id,
                "expires_at": expiry,
                "consent": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return claims, identity, key, offer_hash, message

    def authorization(
        self, session: Session, offer: CredentialOfferRequest
    ) -> CredentialAuthorization:
        offer = CredentialOfferRequest.model_validate_json(offer.model_dump_json())
        claims, _, _, _, message = self._context(session, offer)
        return CredentialAuthorization(
            message=base64.b64encode(message).decode("ascii"), expires_at=claims.valid_until
        )

    def issue(self, session: Session, request: CredentialIssueRequest) -> VerificationCredential:
        request = CredentialIssueRequest.model_validate_json(request.model_dump_json())
        claims, identity, key, offer_hash, message = self._context(session, request)
        try:
            signature = base64.b64decode(request.device_signature, validate=True)
            if (
                not 8 <= len(signature) <= 80
                or base64.b64encode(signature).decode("ascii") != request.device_signature
            ):
                raise ValueError("Invalid signature")
            public_key(identity.public_key_spki).verify(
                signature, message, ec.ECDSA(hashes.SHA256())
            )
        except Exception:
            raise rejected() from None
        row = self.state.db.get(CredentialIssuanceRow, session.session_id)
        purpose = f"credential:{offer_hash}:{key.key_id}"
        if row is not None:
            if (
                row.offer_sha256 != offer_hash
                or row.key_id != key.key_id
                or aware(row.expires_at) <= utcnow()
            ):
                raise rejected()
            cached = VerificationCredential.model_validate(
                self.state.privacy.open_json(session.session_id, purpose, row.payload)
            )
            if cached.claims != claims or cached.key_id != key.key_id:
                raise rejected()
            return cached
        result = self.worker.issue(request.commitment, claims)
        if int(utcnow().timestamp()) >= claims.valid_until:
            raise rejected()
        row = CredentialIssuanceRow(
            session_id=session.session_id,
            offer_sha256=offer_hash,
            key_id=key.key_id,
            expires_at=datetime.fromtimestamp(claims.valid_until, UTC),
            payload=self.state.privacy.seal_json(
                session.session_id, purpose, result.model_dump(mode="json")
            ),
        )
        self.state.db.add(row)
        try:
            # One transaction with the outer request. Never keep a claim after rollback.
            self.state.db.flush()
        except IntegrityError:
            raise rejected() from None
        self.state.privacy.audit(
            session.session_id, actor="session-holder", action="credential_issued"
        )
        return result
