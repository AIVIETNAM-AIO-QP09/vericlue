"""Offline signature checking hashes actual bytes with a separately pinned key."""

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vericlue_api.core.report_signing import ReportSigner

SCRIPT = Path(__file__).resolve().parents[1] / "verify_forensic_report.py"
spec = importlib.util.spec_from_file_location("verify_forensic_report", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture
def bundle(tmp_path):
    key = Ed25519PrivateKey.generate()
    report = tmp_path / "report.html"
    report.write_bytes("<html lang='vi'>Báo cáo tổng hợp</html>".encode())
    signature = tmp_path / "report.sig"
    signature.write_text(
        ReportSigner(key).sign(hashlib.sha256(report.read_bytes()).hexdigest()) + "\n",
        encoding="ascii",
    )
    public = tmp_path / "public.pem"
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return report, signature, public


def run(bundle):
    report, signature, public = bundle
    return cli.main(
        ["--report", str(report), "--signature-file", str(signature), "--public-key", str(public)]
    )


def test_valid_report(bundle, capsys):
    assert run(bundle) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is True
    assert result["report_sha256"] == hashlib.sha256(bundle[0].read_bytes()).hexdigest()
    assert len(result["key_id"]) == 64


@pytest.mark.parametrize(
    "fault",
    [
        "byte",
        "key",
        "signature",
        "mock",
        "missing",
        "empty",
        "size",
        "private-key",
        "signature-size",
    ],
)
def test_failure_is_generic(bundle, capsys, fault, monkeypatch):
    report, signature, public = bundle
    if fault == "byte":
        report.write_bytes(report.read_bytes().replace(b"html", b"HTML", 1))
    elif fault == "key":
        public.write_bytes(
            Ed25519PrivateKey.generate()
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
    elif fault == "signature":
        signature.write_text(base64.b64encode(b"x" * 64).decode(), encoding="ascii")
    elif fault == "mock":
        signature.write_text(
            "MOCK-" + hashlib.sha256(report.read_bytes()).hexdigest(), encoding="ascii"
        )
    elif fault == "missing":
        report.unlink()
    elif fault == "empty":
        report.write_bytes(b"")
    elif fault == "size":
        monkeypatch.setattr(cli, "MAX_REPORT_BYTES", 1)
    elif fault == "signature-size":
        signature.write_bytes(b"x" * 161)
    elif fault == "private-key":
        public.write_bytes(
            Ed25519PrivateKey.generate().private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    assert run(bundle) == 1
    assert json.loads(capsys.readouterr().out) == {"valid": False}
