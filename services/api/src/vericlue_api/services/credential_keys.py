"""Operator-managed public trust registry; no private keys or holder identifiers."""

import hashlib
import re
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import decode
from vericlue_api.db.models import CredentialKeyEventRow, CredentialTrustKeyRow, aware, utcnow
from vericlue_api.schemas.credential import CredentialKey

RETIRED_KEY_GRACE_SECONDS = 60


def key_unavailable() -> ApiError:
    return ApiError(
        409, "credential_key_unavailable", "Khóa chứng nhận chưa sẵn sàng cho yêu cầu này."
    )


def checked_key(value: CredentialKey) -> CredentialKey:
    """Validate canonical public bytes and the exact key fingerprint."""
    value = CredentialKey.model_validate_json(value.model_dump_json())
    public = decode(value.public_key)
    if len(public) != 96 or hashlib.sha256(public).hexdigest() != value.key_id:
        raise ValueError("Invalid public key fingerprint")
    return value


class CredentialKeyRegistry:
    def __init__(self, db: Session, issuer: str) -> None:
        if not isinstance(issuer, str) or re.fullmatch(r"[A-Za-z0-9:/._-]{1,200}", issuer) is None:
            raise ValueError("Configured issuer required")
        self.db, self.issuer = db, issuer

    def resolve(
        self,
        key_id: str | None = None,
        *,
        for_issue: bool = False,
        credential_expires_at: int | None = None,
    ) -> CredentialKey | None:
        """Lock the selected trusted key through verification/issuance and commit."""
        query = select(CredentialTrustKeyRow).where(CredentialTrustKeyRow.issuer == self.issuer)
        query = query.where(
            CredentialTrustKeyRow.key_id == key_id
            if key_id is not None
            else CredentialTrustKeyRow.state == "active"
        )
        # FOR SHARE permits independent proofs but blocks operator state changes.
        row = self.db.scalar(query.with_for_update(read=True))
        allowed = {"active"} if for_issue else {"active", "verify_only"}
        if row is None or row.state not in allowed:
            return None
        if row.state == "verify_only" and (
            row.verify_until is None
            or aware(row.verify_until) <= utcnow()
            or credential_expires_at is not None
            and credential_expires_at > int(aware(row.verify_until).timestamp())
        ):
            return None
        return checked_key(CredentialKey(key_id=row.key_id, public_key=row.public_key))

    def _operator_lock(self) -> None:
        if self.db.bind.dialect.name == "postgresql":
            lock = int.from_bytes(
                hashlib.sha256(("vericlue-bbs-key-operator-v1:" + self.issuer).encode()).digest()[
                    :8
                ],
                "big",
                signed=True,
            )
            self.db.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": lock})

    def _transition(self, row: CredentialTrustKeyRow, state: str) -> None:
        before = row.state
        if before == state:
            return
        if before == "revoked":
            raise key_unavailable()
        row.state, row.changed_at = state, utcnow()
        row.verify_until = (
            row.changed_at + timedelta(seconds=RETIRED_KEY_GRACE_SECONDS)
            if state == "verify_only"
            else None
        )
        self.db.add(CredentialKeyEventRow(key_id=row.key_id, from_state=before, to_state=state))
        self.db.flush()

    def register(self, value: CredentialKey) -> CredentialTrustKeyRow:
        """Stage a reviewed public pin without trusting it; never reactivate a tombstone."""
        value = checked_key(value)
        self._operator_lock()
        row = self.db.scalar(
            select(CredentialTrustKeyRow)
            .where(CredentialTrustKeyRow.key_id == value.key_id)
            .with_for_update()
        )
        if row is not None:
            if row.issuer != self.issuer or row.public_key != value.public_key:
                raise key_unavailable()
            return row
        row = CredentialTrustKeyRow(
            key_id=value.key_id,
            issuer=self.issuer,
            public_key=value.public_key,
            state="staged",
        )
        self.db.add(row)
        self.db.flush()
        self.db.add(CredentialKeyEventRow(key_id=row.key_id, from_state=None, to_state=row.state))
        self.db.flush()
        return row

    def activate(self, key_id: str) -> CredentialTrustKeyRow:
        """Atomically retire the prior issuer key and activate one non-revoked key."""
        self._operator_lock()
        rows = list(
            self.db.scalars(
                select(CredentialTrustKeyRow)
                .where(CredentialTrustKeyRow.issuer == self.issuer)
                .order_by(CredentialTrustKeyRow.key_id)
                .with_for_update()
            )
        )
        target = next((row for row in rows if row.key_id == key_id), None)
        if target is None or target.state == "revoked":
            raise key_unavailable()
        checked_key(CredentialKey(key_id=target.key_id, public_key=target.public_key))
        for row in rows:
            if row.state == "active" and row.key_id != key_id:
                self._transition(row, "verify_only")
        self._transition(target, "active")
        return target

    def revoke(self, key_id: str) -> CredentialTrustKeyRow:
        """Permanently stop trusting every credential issued under this public key."""
        self._operator_lock()
        row = self.db.scalar(
            select(CredentialTrustKeyRow)
            .where(
                CredentialTrustKeyRow.key_id == key_id, CredentialTrustKeyRow.issuer == self.issuer
            )
            .with_for_update()
        )
        if row is None:
            raise key_unavailable()
        self._transition(row, "revoked")
        return row
