"""Read-only BBS configuration/runtime preflight; never creates keys, DB rows or credentials."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))


def main() -> int:
    """Report safe readiness metadata, excluding secrets/paths and biometric acceptance."""
    from starlette.requests import Request

    from vericlue_api.core.config import Settings
    from vericlue_api.core.credential_access import authenticate_verifier
    from vericlue_api.services.credential_verifier_worker import CredentialProofWorker
    from vericlue_api.services.credential_worker import CredentialWorker, run_packet

    try:
        settings = Settings()
        if not settings.private_credentials and not settings.credential_verifier:
            print(json.dumps({"status": "disabled", "runtime_checked": False}))
            return 0
        checks = {}
        if settings.private_credentials:
            node, worker, key = CredentialWorker(settings).paths()
            if not settings.session_privacy or settings.session_master_key is None:
                raise ValueError("Privacy required")
            if (
                len(base64.b64decode(settings.session_master_key.get_secret_value(), validate=True))
                != 32
            ):
                raise ValueError("Privacy key")
            if not settings.result_issuer or not settings.result_audience:
                raise ValueError("Result context")
            settings.result_signer.public_key()  # Load/validate Ed25519; never sign a synthetic pass.
            checks["issuer"] = json.loads(
                run_packet(
                    settings,
                    [
                        str(node),
                        str(worker.with_name("runtime-check.mjs")),
                        "--issuer-key-file",
                        str(key),
                    ],
                    b"",
                )
            )
        if settings.credential_verifier:
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/v1/credentials/challenges",
                    "headers": [],
                }
            )
            rejected = authenticate_verifier(request, settings)
            if rejected is None or rejected.status_code != 401:
                raise ValueError("Verifier access configuration")
            verifier = CredentialProofWorker(settings)
            node, worker, _ = verifier.runtime()
            argv = [str(node), str(worker.with_name("runtime-check.mjs"))]
            if not settings.credential_key_registry:
                verifier.configuration()
                argv += ["--verifier-public-key-file", settings.credential_verifier_public_key_file]
            checks["verifier"] = json.loads(run_packet(settings, argv, b""))
        expected_fields = {"runtime_ok", "issuer_key_id", "verifier_key_id"}
        if any(
            set(value) != expected_fields or value["runtime_ok"] is not True
            for value in checks.values()
        ):
            raise ValueError("Unexpected worker output")
        if (
            settings.private_credentials
            and settings.credential_verifier
            and not settings.credential_key_registry
            and settings.result_issuer == settings.credential_verifier_issuer
            and checks["issuer"]["issuer_key_id"] != checks["verifier"]["verifier_key_id"]
        ):
            raise ValueError("Combined issuer/verifier pins differ")
        print(
            json.dumps(
                {
                    "status": "configuration_ok",
                    "checks": checks,
                    "registry": "not_checked" if settings.credential_key_registry else "disabled",
                    "biometric_acceptance": "not_checked",
                    "ui_consent": "not_checked",
                }
            )
        )
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "error_code": "credential_configuration_invalid"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
