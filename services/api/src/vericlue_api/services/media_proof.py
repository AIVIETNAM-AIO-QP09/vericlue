"""SEC-02 media integrity, not identity enrollment or hardware/camera attestation.

ECDSA P-256/SHA-256 with DER signatures matches Android SHA256withECDSA:
https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ec/
https://developer.android.com/privacy-and-security/keystore
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import MediaProofUseRow
from vericlue_api.services.session_store import Session

VERSION = "vericlue-media-v1"
SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".mp4",
    ".webm",
    ".mov",
    ".wav",
    ".mp3",
    ".m4a",
    ".ogg",
}


def rejected() -> ApiError:
    return ApiError(
        409,
        "media_not_accepted",
        "Không thể tiếp nhận bản ghi. Vui lòng bắt đầu lại lượt xác minh.",
    )


def public_key(spki: str) -> ec.EllipticCurvePublicKey:
    """Only canonical base64 DER SPKI P-256; no certificate/private key/alternate curve."""
    try:
        if not isinstance(spki, str) or not 0 < len(spki) <= 256:
            raise ValueError("Invalid key bounds")
        der = base64.b64decode(spki, validate=True)
        key = serialization.load_der_public_key(der)
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(
            key.curve, ec.SECP256R1
        ):
            raise ValueError("Not P-256")
        canonical = key.public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        if der != canonical or base64.b64encode(der).decode("ascii") != spki:
            raise ValueError("Not canonical SPKI")
        return key
    except Exception as exc:
        raise rejected() from exc


def bind_key(session: Session, spki: str) -> None:
    """Bind once at creation; this does not set device_verified or register an account."""
    public_key(spki)
    session.media_public_key_spki = spki
    renew_nonce(session)


def renew_nonce(session: Session) -> None:
    if session.media_public_key_spki is not None:
        session.challenge.media_nonce = secrets.token_hex(32)


def manifest(
    session: Session,
    stage: str,
    files: dict[str, tuple[str | None, bytes]],
    *,
    audio_offset_ms: int | None = None,
) -> tuple[bytes, str, str]:
    """Canonical ASCII JSON of server-owned context and the exact uploaded bytes/format."""
    attempt = session.challenge.challenge_id if stage == "face" else session.voice_challenge_id
    seed = session.challenge.media_nonce
    expected_roles = {"face": {"image", "video"}, "voice": {"audio", "video"}}
    mandatory = {"face": "image", "voice": "audio"}
    if (
        stage not in expected_roles
        or not files
        or set(files) - expected_roles[stage]
        or mandatory[stage] not in files
        or not isinstance(attempt, str)
        or seed is None
        or re.fullmatch(r"[0-9a-f]{64}", seed) is None
        or session.purpose is None
        or session.nonce is None
    ):
        raise rejected()
    if audio_offset_ms is not None and (
        stage != "voice"
        or "video" not in files
        or type(audio_offset_ms) is not int
        or not -5000 <= audio_offset_ms <= 5000
    ):
        raise rejected()
    nonce = hashlib.sha256(f"{seed}:{stage}:{attempt}".encode("ascii")).hexdigest()
    items = {}
    for role, (filename, data) in files.items():
        if not isinstance(data, bytes) or not 0 < len(data) <= 64 << 20:
            raise rejected()
        suffix = Path(filename or "").suffix.lower()
        items[role] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "suffix": suffix if suffix in SUFFIXES else ".bin",
        }
    body = {
        "protocol": VERSION,
        "session_id": session.session_id,
        "challenge_id": session.challenge.challenge_id,
        "attempt_id": attempt,
        "purpose": session.purpose,
        "client_nonce": session.nonce,
        "stage": stage,
        "nonce": nonce,
        "audio_offset_ms": audio_offset_ms,
        "files": items,
    }
    return (
        json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii"),
        nonce,
        attempt,
    )


def verify_and_consume(
    db: DBSession,
    session: Session,
    stage: str,
    signature: str | None,
    files: dict[str, tuple[str | None, bytes]],
    *,
    required: bool = False,
    audio_offset_ms: int | None = None,
) -> None:
    """Claim in the request transaction; any rejection must roll back that transaction."""
    if session.media_public_key_spki is None and not required:
        if signature is not None:
            raise rejected()  # Never silently ignore a proof or an unbound signer.
        return
    if not session.media_public_key_spki or not signature or len(signature) > 160:
        raise rejected()
    try:
        key = public_key(session.media_public_key_spki)
        signed, nonce, attempt = manifest(session, stage, files, audio_offset_ms=audio_offset_ms)
        der_signature = base64.b64decode(signature, validate=True)
        if (
            not 8 <= len(der_signature) <= 80
            or base64.b64encode(der_signature).decode("ascii") != signature
        ):
            raise ValueError("Invalid signature bounds")
        key.verify(der_signature, signed, ec.ECDSA(hashes.SHA256()))
    except Exception as exc:
        raise rejected() from exc
    record = MediaProofUseRow(
        nonce_hash=hashlib.sha256(nonce.encode("ascii")).hexdigest(),
        session_id=session.session_id,
        attempt_id=attempt,
        stage=stage,
        manifest_sha256=hashlib.sha256(signed).hexdigest(),
        key_fingerprint=hashlib.sha256(base64.b64decode(session.media_public_key_spki)).hexdigest(),
    )
    try:
        # No savepoint here: SQLite's legacy transaction mode may release its
        # first SAVEPOINT before an outer SQL BEGIN, persisting a failed upload's
        # claim. A normal INSERT starts the transaction on both SQLite/Postgres.
        db.add(record)
        db.flush()
    except IntegrityError as exc:
        raise rejected() from exc


def require_consumed(db: DBSession, session: Session, stage: str, *, required: bool) -> None:
    """A server mode change or an old snapshot must not skip upload verification."""
    if not required and session.media_public_key_spki is None:
        return
    attempt = session.challenge.challenge_id if stage == "face" else session.voice_challenge_id
    seed = session.challenge.media_nonce
    if not seed or not attempt or not session.media_public_key_spki:
        raise rejected()
    nonce = hashlib.sha256(f"{seed}:{stage}:{attempt}".encode("ascii")).hexdigest()
    row = db.get(MediaProofUseRow, hashlib.sha256(nonce.encode("ascii")).hexdigest())
    if row is None or (row.session_id, row.attempt_id, row.stage) != (
        session.session_id,
        attempt,
        stage,
    ):
        raise rejected()
    fingerprint = hashlib.sha256(
        base64.b64decode(session.media_public_key_spki, validate=True)
    ).hexdigest()
    if row.key_fingerprint != fingerprint:
        raise rejected()
