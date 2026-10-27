"""Opt-in bounded BBS worker; the child receives no API keys, DB access or holder secret."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from contextlib import suppress
from pathlib import Path
from threading import BoundedSemaphore, Thread

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import decode
from vericlue_api.schemas.credential import (
    CredentialKey,
    VerificationClaims,
    VerificationCredential,
)

_SLOT = BoundedSemaphore(1)
_ENV = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "LANG", "LC_ALL"}


def unavailable() -> ApiError:
    return ApiError(503, "credential_unavailable", "Chưa thể cấp chứng nhận lúc này.")


class CredentialWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def paths(self) -> tuple[Path, Path, Path]:
        node, worker, key = (
            Path(value or "")
            for value in (
                self.settings.credential_node,
                self.settings.credential_worker_file,
                self.settings.credential_signing_key_file,
            )
        )
        if (
            not self.settings.private_credentials
            or not all(p.is_absolute() and p.is_file() for p in (node, worker, key))
            or worker.name != "issuer-worker.mjs"
        ):
            raise unavailable()
        return node, worker, key

    def public_key(self) -> CredentialKey:
        try:
            _, _, key = self.paths()
            if key.stat().st_size > 2048:
                raise ValueError("Invalid key")
            bundle = json.loads(key.read_text(encoding="utf-8"))
            if (
                set(bundle) != {"version", "secret_key", "public_key"}
                or type(bundle["version"]) is not int
                or bundle["version"] != 1
                or len(decode(bundle["secret_key"])) != 32
            ):
                raise ValueError("Invalid key")
            public = decode(bundle["public_key"])
            if len(public) != 96:
                raise ValueError("Invalid key")
            return CredentialKey(
                key_id=hashlib.sha256(public).hexdigest(), public_key=bundle["public_key"]
            )
        except Exception:
            raise unavailable() from None

    def issue(self, commitment: str, claims: VerificationClaims) -> VerificationCredential:
        claims = VerificationClaims.model_validate_json(claims.model_dump_json())
        node, worker, key = self.paths()
        expected = self.public_key()
        packet = json.dumps(
            {"commitment": commitment, "claims": claims.model_dump(mode="json")},
            separators=(",", ":"),
        ).encode("ascii")
        if len(packet) > 4096 or not _SLOT.acquire(blocking=False):
            raise unavailable()
        process = None
        reader = None
        output: list[bytes] = []
        try:
            process = subprocess.Popen(
                [str(node), str(worker), "--key-file", str(key)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={k: v for k, v in os.environ.items() if k.upper() in _ENV},
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
            )

            def read() -> None:
                chunk = process.stdout.read(8193)
                output.append(chunk)
                if len(chunk) > 8192 and process.poll() is None:
                    process.kill()

            reader = Thread(target=read, name="vericlue-credential-output", daemon=True)
            reader.start()
            process.stdin.write(packet)
            process.stdin.close()
            process.wait(timeout=self.settings.credential_timeout_seconds)
            reader.join(timeout=1)
            if (
                reader.is_alive()
                or process.returncode != 0
                or len(output) != 1
                or len(output[0]) > 8192
            ):
                raise ValueError("Invalid worker response")
            result = VerificationCredential.model_validate_json(output[0])
            if result.claims != claims or result.key_id != expected.key_id:
                raise ValueError("Invalid worker context")
            # Strict canonical encodings as well as shape/size; holder checks BBS signature.
            if len(decode(result.signature)) != 80:
                raise ValueError("Invalid signature")
            return result
        except Exception:
            raise unavailable() from None
        finally:
            try:
                with suppress(OSError, subprocess.SubprocessError):
                    if process is not None:
                        if process.poll() is None:
                            process.kill()
                        process.wait(timeout=5)
                        if reader is not None:
                            reader.join(timeout=1)
                        for pipe in (process.stdin, process.stdout):
                            if pipe is not None:
                                pipe.close()
            finally:
                _SLOT.release()
