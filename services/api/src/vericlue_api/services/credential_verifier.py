"""Durable one-use challenges, atomically consumed only after BBS verification."""

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import decode
from vericlue_api.db.models import CredentialChallengeRow, aware, utcnow
from vericlue_api.schemas.credential import (
    VerificationAccepted,
    VerificationChallenge,
    VerificationPresentation,
    VerificationRejected,
    https_origin,
)
from vericlue_api.services.credential_verifier_worker import CredentialProofWorker

CHALLENGE_SECONDS = 60
MAX_PENDING_PER_AUDIENCE = 128


class CredentialVerifier:
    def __init__(self, settings: Settings, db: Session, audience: str) -> None:
        self.db = db
        self.audience = https_origin(audience)
        self.worker = CredentialProofWorker(settings)

    def challenge(self) -> VerificationChallenge:
        """Issue a verifier-owned context with a transactionally bounded pending set."""
        _, _, key, issuer = self.worker.configuration()
        if self.db.bind.dialect.name == "postgresql":
            # Stable per-audience lock coordinates capacity across independent API workers.
            lock = int.from_bytes(
                hashlib.sha256(("vericlue-bbs-challenge-v1:" + self.audience).encode()).digest()[
                    :8
                ],
                "big",
                signed=True,
            )
            self.db.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": lock})
        now = int(utcnow().timestamp())
        moment = datetime.fromtimestamp(now, UTC)
        self.db.execute(
            delete(CredentialChallengeRow).where(
                CredentialChallengeRow.expires_at <= moment,
            )
        )
        pending = self.db.scalar(
            select(func.count())
            .select_from(CredentialChallengeRow)
            .where(
                CredentialChallengeRow.audience == self.audience,
                CredentialChallengeRow.expires_at > moment,
            )
        )
        if pending >= MAX_PENDING_PER_AUDIENCE:
            raise ApiError(503, "credential_challenge_capacity", "Chưa thể tạo lượt kiểm tra mới.")
        result = VerificationChallenge(
            id=secrets.token_urlsafe(16),
            nonce=secrets.token_urlsafe(32),
            audience=self.audience,
            issued_at=now,
            expires_at=now + CHALLENGE_SECONDS,
        )
        self.db.add(
            CredentialChallengeRow(
                challenge_id=result.id,
                audience=result.audience,
                issuer=issuer,
                key_id=key.key_id,
                nonce=result.nonce,
                issued_at=moment,
                expires_at=datetime.fromtimestamp(result.expires_at, UTC),
            )
        )
        self.db.flush()
        return result

    def verify(
        self, presentation: VerificationPresentation
    ) -> VerificationAccepted | VerificationRejected:
        """Hold the database row lock through crypto and consume before sending success."""
        presentation = VerificationPresentation.model_validate_json(presentation.model_dump_json())
        _, _, key, issuer = self.worker.configuration()
        row = self.db.scalar(
            select(CredentialChallengeRow)
            .where(
                CredentialChallengeRow.challenge_id == presentation.challenge_id,
                CredentialChallengeRow.audience == self.audience,
            )
            .with_for_update()
        )
        now = int(utcnow().timestamp())
        c = presentation.disclosed
        if (
            row is None
            or row.key_id != key.key_id
            or row.issuer != issuer
            or c.issuer != issuer
            or not int(aware(row.issued_at).timestamp())
            <= now
            < int(aware(row.expires_at).timestamp())
            or not c.valid_from <= now < c.valid_until
        ):
            return VerificationRejected()
        q = VerificationChallenge(
            id=row.challenge_id,
            nonce=row.nonce,
            audience=row.audience,
            issued_at=int(aware(row.issued_at).timestamp()),
            expires_at=int(aware(row.expires_at).timestamp()),
        )
        try:
            if len(decode(presentation.proof)) != 496 or len(decode(presentation.pseudonym)) != 48:
                return VerificationRejected()
        except ValueError:
            return VerificationRejected()
        if not self.worker.verify(q, presentation):
            return VerificationRejected()
        # Recheck after CPU/queue/IO, not only when accepting the request.
        finished = int(utcnow().timestamp())
        if not max(q.issued_at, c.valid_from) <= finished < min(q.expires_at, c.valid_until):
            return VerificationRejected()
        self.db.delete(row)
        self.db.flush()
        return VerificationAccepted(disclosed=c, pseudonym=presentation.pseudonym)
