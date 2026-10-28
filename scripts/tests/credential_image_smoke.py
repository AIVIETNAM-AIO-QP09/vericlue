"""Executed only inside the CI container: ephemeral tmpfs keys, no network/DB/issuance."""

import base64
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    """Verify the shipped native runtime/key checks as the unprivileged API user."""
    assert os.getuid() == 10001
    package = Path("/app/services/credentials")
    assert (package / "dist/holder.mjs").is_file()
    assert (package / "dist/LICENSES.txt").is_file()
    assert not (package / "node_modules/esbuild").exists()
    assert Path("/usr/local/share/doc/node/LICENSE").is_file()
    with TemporaryDirectory() as directory:
        secret, public = Path(directory) / "bbs-private.json", Path(directory) / "bbs-public.json"
        for script, args in (
            ("keygen.mjs", ["--out", str(secret)]),
            ("export-public-key.mjs", ["--key-file", str(secret), "--out", str(public)]),
        ):
            subprocess.run(
                ["/usr/local/bin/node", str(package / script), *args],
                capture_output=True,
                check=True,
                timeout=15,
            )
        result = Path(directory) / "result.pem"
        result.write_bytes(
            Ed25519PrivateKey.generate().private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        env = {
            **os.environ,
            "PRIVATE_CREDENTIALS": "true",
            "CREDENTIAL_VERIFIER": "true",
            "SESSION_PRIVACY": "true",
            "SESSION_MASTER_KEY": base64.b64encode(secrets.token_bytes(32)).decode(),
            "RESULT_SIGNING_KEY_FILE": str(result),
            "RESULT_ISSUER": "https://vericlue.example",
            "RESULT_AUDIENCE": "demo-integrator",
            "CREDENTIAL_NODE": "/usr/local/bin/node",
            "CREDENTIAL_WORKER_FILE": str(package / "issuer-worker.mjs"),
            "CREDENTIAL_SIGNING_KEY_FILE": str(secret),
            "CREDENTIAL_VERIFIER_WORKER_FILE": str(package / "verifier-worker.mjs"),
            "CREDENTIAL_VERIFIER_PUBLIC_KEY_FILE": str(public),
            "CREDENTIAL_VERIFIER_ISSUER": "https://vericlue.example",
            "CREDENTIAL_VERIFIER_TOKENS": json.dumps(
                {secrets.token_urlsafe(32): "https://service.example"}
            ),
        }
        checked = subprocess.run(
            [sys.executable, "/app/scripts/check_credentials.py"],
            env=env,
            capture_output=True,
            timeout=15,
        )
        assert checked.returncode == 0, "packaged preflight failed"
        value = json.loads(checked.stdout)
        assert (
            value["status"] == "configuration_ok" and value["biometric_acceptance"] == "not_checked"
        )
        assert (
            value["checks"]["issuer"]["issuer_key_id"]
            == value["checks"]["verifier"]["verifier_key_id"]
        )
    print("Container BBS runtime/key checks passed; no credential or biometric verdict issued.")


if __name__ == "__main__":
    main()
