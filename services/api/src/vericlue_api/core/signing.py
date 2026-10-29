"""Ed25519 primitives and a small, domain-separated result envelope (not JWT).

Uses cryptography 50; never negotiates algorithms or fetches keys from a token:
https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from vericlue_api.schemas.result import ResultClaims, SignedResult, SigningKey

DOMAIN = b"vericlue-session-result-v1\x00"


def public_key_fingerprint(key: Ed25519PublicKey) -> str:
    """SHA-256 of public DER SPKI; accept only the protocol's pinned curve."""
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Ed25519 public key required")
    return hashlib.sha256(
        key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).hexdigest()


def sign(payload: bytes, key: Ed25519PrivateKey) -> bytes:
    """Sign exact bytes; protocols must supply their own domain separator."""
    return key.sign(payload)


def verify(payload: bytes, signature: bytes, key: Ed25519PublicKey) -> bool:
    """Signature validity only; not an authorization or a biometric decision."""
    if not isinstance(key, Ed25519PublicKey):
        return False
    try:
        key.verify(signature, payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def load_private_key(path: Path) -> Ed25519PrivateKey:
    """Load a bounded, configured Ed25519 PEM; never generate a fallback key."""
    if not path.is_file() or not 0 < path.stat().st_size <= 4096:
        raise ValueError("Signing key unavailable")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Ed25519 key required")
    return key


def load_public_key(path: Path) -> Ed25519PublicKey:
    """Load the integrator's trusted Ed25519 public PEM."""
    if not path.is_file() or not 0 < path.stat().st_size <= 4096:
        raise ValueError("Verification key unavailable")
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Ed25519 key required")
    return key


def encode(raw: bytes) -> str:
    """Canonical unpadded base64url."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode(value: str) -> bytes:
    """Reject padding, alternate alphabet, excess size and non-canonical pad bits."""
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("Invalid encoding")
    raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if encode(raw) != value:
        raise ValueError("Non-canonical encoding")
    return raw


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


class ResultSigner:
    def __init__(self, key: Ed25519PrivateKey) -> None:
        self._key = key
        self.key_id = public_key_fingerprint(key.public_key())

    def public_key(self) -> SigningKey:
        der = self._key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return SigningKey(key_id=self.key_id, public_key_spki=base64.b64encode(der).decode("ascii"))

    def issue(self, claims: ResultClaims) -> SignedResult:
        # Revalidate model_copy() instances too. No paths, scores, vectors or extra fields.
        claims = ResultClaims.model_validate_json(claims.model_dump_json(exclude_none=True))
        raw = json.dumps(
            claims.model_dump(exclude_none=True),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        signature = sign(DOMAIN + self.key_id.encode("ascii") + b"\x00" + raw, self._key)
        return SignedResult(
            algorithm="Ed25519",
            key_id=self.key_id,
            payload=encode(raw),
            signature=encode(signature),
        )


def verify_result(
    envelope: SignedResult,
    key: Ed25519PublicKey,
    *,
    issuer: str,
    audience: str,
    session_id: str,
    nonce: str,
    purpose: str,
    now: int,
) -> ResultClaims:
    """Verify pinned key, exact signature, strict claims/context/time; no network access.

    The integrator must consume result_id atomically with its own business action.
    Signature validity does not make a result reusable or a decision into a pass.
    """
    try:
        envelope = SignedResult.model_validate_json(envelope.model_dump_json())
        kid = public_key_fingerprint(key)
        if envelope.key_id != kid:
            raise ValueError("Key mismatch")
        raw, signature = decode(envelope.payload), decode(envelope.signature)
        if not verify(DOMAIN + kid.encode("ascii") + b"\x00" + raw, signature, key):
            raise ValueError("Signature mismatch")
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_unique_object)
        claims = ResultClaims.model_validate(value)
        if (
            claims.issuer != issuer
            or claims.audience != audience
            or claims.session_id != session_id
            or claims.nonce != nonce
            or claims.purpose != purpose
            or type(now) is not int
            or not claims.issued_at <= now < claims.expires_at
        ):
            raise ValueError("Context or expiry mismatch")
        return claims
    except Exception as exc:
        raise ValueError("Result not accepted") from exc
