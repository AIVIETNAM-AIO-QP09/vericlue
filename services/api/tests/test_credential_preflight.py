"""Read-only operational checks use real crypto, never an accepted biometric decision."""

import base64
import importlib.util
import json
import os
import secrets
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "credential_preflight", ROOT / "scripts/check_credentials.py"
)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def test_disabled_preflight_does_not_claim_runtime_checked(capsys):
    assert CHECK.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "disabled", "runtime_checked": False}


def test_missing_configuration_fails_without_printing_secrets(monkeypatch, capsys):
    monkeypatch.setenv("PRIVATE_CREDENTIALS", "true")
    monkeypatch.setenv("SESSION_MASTER_KEY", "do-not-print-master-key")
    assert CHECK.main() == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "error_code": "credential_configuration_invalid",
    }


@pytest.mark.skipif(
    not os.environ.get("TEST_CREDENTIAL_NODE"), reason="opt-in actual Node BBS runtime"
)
@pytest.mark.parametrize("role", ["issuer", "verifier", "both"])
def test_native_preflight_checks_keys_without_signing_or_database(
    tmp_path, monkeypatch, capsys, role
):
    from vericlue_api.core.signing import ResultSigner
    from vericlue_api.db.database import Database

    monkeypatch.setattr(
        Database, "__init__", lambda *a, **k: pytest.fail("preflight must not open DB")
    )
    monkeypatch.setattr(
        ResultSigner, "issue", lambda *a, **k: pytest.fail("preflight must not sign a decision")
    )
    node = os.environ["TEST_CREDENTIAL_NODE"]
    package = ROOT / "services/credentials"
    secret, public = tmp_path / "bbs-private.json", tmp_path / "bbs-public.json"
    for script, args in (
        ("keygen.mjs", ["--out", str(secret)]),
        ("export-public-key.mjs", ["--key-file", str(secret), "--out", str(public)]),
    ):
        subprocess.run(
            [node, str(package / script), *args], capture_output=True, check=True, timeout=15
        )
    result = tmp_path / "result.pem"
    result.write_bytes(
        Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    token = secrets.token_urlsafe(32)
    env = {
        "PRIVATE_CREDENTIALS": "true" if role != "verifier" else "false",
        "CREDENTIAL_VERIFIER": "true" if role != "issuer" else "false",
        "SESSION_PRIVACY": "true",
        "SESSION_MASTER_KEY": base64.b64encode(secrets.token_bytes(32)).decode(),
        "RESULT_SIGNING_KEY_FILE": str(result),
        "RESULT_ISSUER": "https://vericlue.example",
        "RESULT_AUDIENCE": "demo-integrator",
        "CREDENTIAL_NODE": node,
        "CREDENTIAL_WORKER_FILE": str(package / "issuer-worker.mjs"),
        "CREDENTIAL_SIGNING_KEY_FILE": str(secret),
        "CREDENTIAL_VERIFIER_WORKER_FILE": str(package / "verifier-worker.mjs"),
        "CREDENTIAL_VERIFIER_PUBLIC_KEY_FILE": str(public),
        "CREDENTIAL_VERIFIER_ISSUER": "https://vericlue.example",
        "CREDENTIAL_VERIFIER_TOKENS": json.dumps({token: "https://service.example"}),
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    before = {path: path.read_bytes() for path in (secret, public, result)}
    assert CHECK.main() == 0
    output = capsys.readouterr().out
    value = json.loads(output)
    assert value["status"] == "configuration_ok" and value["biometric_acceptance"] == "not_checked"
    assert value["ui_consent"] == "not_checked"
    assert token not in output and env["SESSION_MASTER_KEY"] not in output
    assert all(path.read_bytes() == raw for path, raw in before.items())
    if role != "verifier":
        damaged = json.loads(secret.read_bytes())
        damaged["secret_key"] = (
            base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
        )
        secret.write_text(json.dumps(damaged), encoding="utf-8")
        assert CHECK.main() == 2
        assert json.loads(capsys.readouterr().out)["status"] == "failed"
    else:
        monkeypatch.setenv("CREDENTIAL_VERIFIER_TOKENS", "{}")
        assert CHECK.main() == 2
        assert json.loads(capsys.readouterr().out)["status"] == "failed"
