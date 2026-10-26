"""Detached Ed25519 signatures for exact HTML report bytes, separate from session results."""

from __future__ import annotations

import base64
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from vericlue_api.core.signing import public_key_fingerprint, sign, verify
from vericlue_api.schemas.result import SigningKey

DOMAIN = b"vericlue-forensic-html-report-v1\x00"


def _message(digest: str, key: Ed25519PublicKey) -> bytes:
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Canonical SHA-256 required")
    return DOMAIN + public_key_fingerprint(key).encode("ascii") + b"\x00" + bytes.fromhex(digest)


def verify_report_digest(digest: str, signature: str, key: Ed25519PublicKey) -> bool:
    """Verify a digest using a caller-pinned key; never trust a key inside the report."""
    try:
        if (
            not isinstance(key, Ed25519PublicKey)
            or not isinstance(signature, str)
            or len(signature) != 88
        ):
            return False
        raw = base64.b64decode(signature, validate=True)
        if len(raw) != 64 or base64.b64encode(raw).decode("ascii") != signature:
            return False
        return verify(_message(digest, key), raw, key)
    except (TypeError, ValueError):
        return False


class ReportSigner:
    def __init__(self, key: Ed25519PrivateKey) -> None:
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("Ed25519 private key required")
        self._key = key
        self.key_id = public_key_fingerprint(key.public_key())

    def public_key(self) -> SigningKey:
        """Public DER SPKI and SHA-256 fingerprint; no private key bytes."""
        der = self._key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return SigningKey(key_id=self.key_id, public_key_spki=base64.b64encode(der).decode("ascii"))

    def sign(self, digest: str) -> str:
        """Sign only the digest of the server-produced report, with this protocol's domain."""
        return base64.b64encode(sign(_message(digest, self._key.public_key()), self._key)).decode(
            "ascii"
        )

    def verify(self, digest: str, signature: str) -> bool:
        """Verify with the current configured key; signing does not certify model quality."""
        return verify_report_digest(digest, signature, self._key.public_key())
