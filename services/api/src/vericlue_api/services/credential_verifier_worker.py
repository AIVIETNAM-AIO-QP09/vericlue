"""Public-key-only BBS verification through the bounded Node subprocess boundary."""

import hashlib
import json
from pathlib import Path

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import decode
from vericlue_api.schemas.credential import (
    CredentialKey,
    VerificationAccepted,
    VerificationChallenge,
    VerificationPresentation,
)
from vericlue_api.services.credential_worker import run_packet


def unavailable() -> ApiError:
    return ApiError(503, "credential_verifier_unavailable", "Chưa thể kiểm tra chứng nhận lúc này.")


class CredentialProofWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def configuration(self) -> tuple[Path, Path, CredentialKey, str]:
        try:
            node = Path(self.settings.credential_node or "")
            worker = Path(self.settings.credential_verifier_worker_file or "")
            key = Path(self.settings.credential_verifier_public_key_file or "")
            issuer = self.settings.credential_verifier_issuer
            if (
                not self.settings.credential_verifier
                or not issuer
                or not all(p.is_absolute() and p.is_file() for p in (node, worker, key))
                or worker.name != "verifier-worker.mjs"
                or key.stat().st_size > 2048
            ):
                raise ValueError("Invalid configuration")
            pinned = CredentialKey.model_validate_json(key.read_bytes())
            public = decode(pinned.public_key)
            if len(public) != 96 or hashlib.sha256(public).hexdigest() != pinned.key_id:
                raise ValueError("Invalid pin")
            return node, worker, pinned, issuer
        except Exception:
            raise unavailable() from None

    def verify(
        self, challenge: VerificationChallenge, presentation: VerificationPresentation
    ) -> bool:
        try:
            node, worker, pinned, issuer = self.configuration()
            packet = json.dumps(
                {
                    "public_key": pinned.public_key,
                    "issuer": issuer,
                    "audience": challenge.audience,
                    "challenge": challenge.model_dump(mode="json"),
                    "presentation": presentation.model_dump(mode="json"),
                },
                separators=(",", ":"),
            ).encode("ascii")
            raw = run_packet(self.settings, [str(node), str(worker)], packet)
            result = json.loads(raw)
            if result == {"valid": False} and type(result["valid"]) is bool:
                return False
            if not isinstance(result, dict) or set(result) != {
                "valid",
                "assurance",
                "disclosed",
                "pseudonym",
            }:
                raise ValueError("Invalid worker response")
            # An accepted child response must echo exactly the checked public claims.
            accepted = VerificationAccepted.model_validate_json(raw)
            if (
                type(result["valid"]) is not bool
                or accepted.disclosed != presentation.disclosed
                or accepted.pseudonym != presentation.pseudonym
            ):
                raise ValueError("Invalid worker response")
            return True
        except Exception:
            raise unavailable() from None
