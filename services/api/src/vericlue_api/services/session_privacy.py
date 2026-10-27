"""SEC-01 authenticated encryption and bounded plaintext leases for native inference.

AES-GCM recipe: https://cryptography.io/en/stable/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM
Fresh random 96-bit nonce per encryption; AAD binds session and artifact purpose.
Per-session random DEKs are wrapped by a separately configured 256-bit master key.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import tempfile
from concurrent.futures import Future
from pathlib import Path
from threading import Lock, Thread
from time import monotonic, sleep

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import AccessEventRow, SessionKeyRow, SessionRow, utcnow
from vericlue_api.services.audit_log import GENESIS_HASH, compute_hash

MAGIC = b"VCL1"


def unavailable() -> ApiError:
    return ApiError(503, "privacy_unavailable", "Không thể truy cập dữ liệu phiên lúc này.")


class PlaintextLease:
    """Keep decoded files until every native inference future has actually finished."""

    def __init__(self, directory: tempfile.TemporaryDirectory) -> None:
        self.directory = directory
        self._refs = 1
        self._lock = Lock()

    def retain(self, future: Future) -> None:
        with self._lock:
            self._refs += 1
        future.add_done_callback(lambda _: self.release())

    def release(self) -> None:
        with self._lock:
            self._refs -= 1
            remove = self._refs == 0
        if remove:
            try:
                self.directory.cleanup()
            except OSError:
                # A timed-out subprocess is reaped asynchronously; Windows can
                # keep its decoder handle open briefly after the IPC call ends.
                def retry():
                    deadline = monotonic() + 30
                    while monotonic() < deadline:
                        sleep(0.1)
                        try:
                            self.directory.cleanup()
                            return
                        except OSError:
                            continue
                    logging.getLogger(__name__).error("plaintext_lease_cleanup_failed")

                Thread(target=retry, name="vericlue-media-cleanup", daemon=False).start()


class SessionPrivacy:
    """Request-scoped DB owner; no database/session/key is sent into ML workers."""

    def __init__(self, settings: Settings, db: DBSession) -> None:
        self.settings, self.db = settings, db

    @property
    def enabled(self) -> bool:
        return self.settings.session_privacy

    def _master(self) -> bytes:
        try:
            if not self.enabled or self.settings.session_master_key is None:
                raise ValueError("Missing master")
            key = base64.b64decode(
                self.settings.session_master_key.get_secret_value(), validate=True
            )
            if len(key) != 32:
                raise ValueError("Invalid key length")
            return key
        except Exception as exc:
            raise unavailable() from exc

    @staticmethod
    def _aad(session_id: str, purpose: str) -> bytes:
        return json.dumps(["vericlue-session-v1", session_id, purpose]).encode("utf-8")

    @staticmethod
    def _seal(key: bytes, data: bytes, aad: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, aad)

    @staticmethod
    def _open(key: bytes, data: bytes, aad: bytes) -> bytes:
        if not data.startswith(MAGIC) or len(data) < 32:
            raise ValueError("Invalid encrypted artifact")
        return AESGCM(key).decrypt(data[4:16], data[16:], aad)

    def _key(self, session_id: str, *, create: bool = False) -> bytes:
        master = self._master()
        row = self.db.scalar(
            select(SessionKeyRow).where(SessionKeyRow.session_id == session_id).with_for_update()
        )
        try:
            if row is None:
                if not create:
                    raise ValueError("Missing session key")
                key = AESGCM.generate_key(bit_length=256)
                row = SessionKeyRow(
                    session_id=session_id,
                    wrapped_key=base64.b64encode(
                        self._seal(master, key, self._aad(session_id, "dek"))
                    ).decode("ascii"),
                )
                self.db.add(row)
                self.db.flush()
                return key
            if row.destroyed_at is not None or row.wrapped_key is None:
                raise ApiError(410, "data_expired", "Dữ liệu phiên đã hết thời hạn lưu trữ.")
            return self._open(
                master,
                base64.b64decode(row.wrapped_key, validate=True),
                self._aad(session_id, "dek"),
            )
        except ApiError:
            raise
        except Exception as exc:
            raise unavailable() from exc

    def seal_json(self, session_id: str, purpose: str, value: dict) -> dict:
        """Encrypt sensitive JSON; existing callers keep plain behavior only when flag is off."""
        if not self.enabled:
            return value
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
        sealed = self._seal(
            self._key(session_id, create=True), data, self._aad(session_id, purpose)
        )
        return {"encrypted_session_v1": base64.b64encode(sealed).decode("ascii")}

    def open_json(self, session_id: str, purpose: str, value: dict) -> dict:
        """Ciphertext never falls back to plaintext after key/configuration/integrity failure."""
        if "encrypted_session_v1" not in value:
            if self.enabled:
                raise unavailable()
            return value
        try:
            clear = self._open(
                self._key(session_id),
                base64.b64decode(value["encrypted_session_v1"], validate=True),
                self._aad(session_id, purpose),
            )
            result = json.loads(clear)
            if not isinstance(result, dict):
                raise ValueError("Not an object")
            return result
        except ApiError:
            raise
        except Exception as exc:
            raise unavailable() from exc

    def seal_media(self, session_id: str, name: str, data: bytes) -> bytes:
        """Bind a media blob to its server-issued filename and session."""
        if not self.enabled:
            return data
        return self._seal(self._key(session_id), data, self._aad(session_id, "media:" + name))

    def prepare(self, session_id: str | None, kwargs: dict) -> tuple[dict, PlaintextLease | None]:
        """Decode bounded media under MEDIA_DIR for native path-only readers, with a lease."""
        if not self.enabled or not session_id or not session_id.startswith("ses_"):
            return kwargs, None
        paths = [*kwargs.get("images", [])]
        paths.extend(
            kwargs[k]
            for k in ("reference_image", "reference_video", "video", "audio")
            if kwargs.get(k)
        )
        if not paths:
            return kwargs, None
        root = Path(self.settings.media_dir).resolve()
        expected = root / session_id
        if expected.parent != root:
            raise unavailable()
        decoded = root / "_decoded"
        if decoded.is_symlink() or decoded.is_junction():
            raise unavailable()
        decoded.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(prefix="lease-", dir=decoded)
        lease = PlaintextLease(directory)
        remap = {}
        try:
            key = self._key(session_id)
            for index, path in enumerate(dict.fromkeys(paths)):
                path = Path(path)
                if (
                    path.is_symlink()
                    or path.parent.is_symlink()
                    or path.parent.is_junction()
                    or path.resolve().parent != expected
                    or not 0 < path.stat().st_size <= (64 << 20) + 32
                ):
                    raise ValueError("Untrusted encrypted input")
                clear = self._open(
                    key, path.read_bytes(), self._aad(session_id, "media:" + path.name)
                )
                target = Path(directory.name) / f"{index}{path.suffix}"
                target.write_bytes(clear)
                remap[path] = target
            updated = dict(kwargs)
            if "images" in updated:
                updated["images"] = [remap[Path(p)] for p in updated["images"]]
            for role in ("reference_image", "reference_video", "video", "audio"):
                if updated.get(role):
                    updated[role] = remap[Path(updated[role])]
            return updated, lease
        except Exception as exc:
            lease.release()
            raise unavailable() from exc

    def audit(self, scope: str, *, actor: str, action: str) -> None:
        """Append a PII-free event; caller holds the scope's session/account row lock."""
        previous = self.db.scalar(
            select(AccessEventRow)
            .where(AccessEventRow.scope == scope)
            .order_by(AccessEventRow.id.desc())
            .limit(1)
        )
        payload = {"scope": scope, "actor": actor, "action": action, "at": utcnow().isoformat()}
        prev_hash = previous.hash if previous is not None else GENESIS_HASH
        self.db.add(
            AccessEventRow(
                scope=scope,
                actor=actor,
                action=action,
                prev_hash=prev_hash,
                hash=compute_hash(prev_hash, payload),
                payload=payload,
            )
        )
        self.db.flush()

    def destroy(self, session_id: str) -> None:
        """Retain a tombstone so a destroyed key cannot be silently recreated."""
        row = self.db.get(SessionKeyRow, session_id)
        if row is not None and row.destroyed_at is None:
            row.wrapped_key, row.destroyed_at = None, utcnow()
            self.audit(session_id, actor="system-cleanup", action="key_destroyed")

    def lock_session(self, session_id: str) -> None:
        """Serialize access-audit appends without relying solely on a hash-chain index."""
        self.db.scalar(
            select(SessionRow).where(SessionRow.session_id == session_id).with_for_update()
        )
