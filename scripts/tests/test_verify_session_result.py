"""CLI verifies a pinned key/context; valid negative decisions remain negative."""

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vericlue_api.core.signing import ResultSigner
from vericlue_api.schemas.result import ResultClaims

SCRIPT = Path(__file__).resolve().parents[1] / "verify_session_result.py"
spec = importlib.util.spec_from_file_location("vericlue_verify_result_test", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.mark.parametrize("status", ["pass", "deny", "recovery_required"])
def test_cli_validity_is_not_an_authorization_result(tmp_path, capsys, status):
    key = Ed25519PrivateKey.generate()
    public = tmp_path / "public.pem"
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    now = int(datetime.now(UTC).timestamp())
    claims = ResultClaims(
        version=1,
        issuer="vericlue-demo",
        audience="integrator-demo",
        result_id="res_" + "a" * 64,
        session_id="ses_cli",
        purpose="reauth",
        nonce="synthetic_nonce_123456",
        status=status,
        issued_at=now,
        expires_at=now + 60,
        account_id="acct_" + "b" * 32 if status == "pass" else None,
        device_id="dev_" + "c" * 32 if status == "pass" else None,
    )
    envelope = ResultSigner(key).issue(claims)
    path = tmp_path / "result.json"
    path.write_text(envelope.model_dump_json())
    arguments = [
        "--result",
        str(path),
        "--public-key",
        str(public),
        "--issuer",
        claims.issuer,
        "--audience",
        claims.audience,
        "--session-id",
        claims.session_id,
        "--nonce",
        claims.nonce,
        "--purpose",
        "reauth",
    ]
    assert cli.main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["status"] == status
    arguments[arguments.index("--nonce") + 1] = "different_nonce_12345"
    assert cli.main(arguments) == 1
    assert json.loads(capsys.readouterr().out) == {"valid": False}
