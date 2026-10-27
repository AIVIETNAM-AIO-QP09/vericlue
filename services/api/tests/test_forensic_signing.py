"""Real signatures and synthetic reports/media; never biometric accuracy claims."""

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from test_forensic_real import _run
from test_forensic_real import real_client as real_client

from vericlue_api.core.config import get_settings
from vericlue_api.core.report_signing import DOMAIN, ReportSigner, verify_report_digest
from vericlue_api.core.signing import DOMAIN as RESULT_DOMAIN
from vericlue_api.core.signing import load_private_key, public_key_fingerprint
from vericlue_api.db.models import ForensicJobRow
from vericlue_api.main import create_app

DIGEST = hashlib.sha256("Báo cáo tổng hợp".encode()).hexdigest()


def test_sign_verify_and_protocol_is_not_raw_digest_or_session_signature():
    key = Ed25519PrivateKey.generate()
    signer = ReportSigner(key)
    signature = signer.sign(DIGEST)
    raw = base64.b64decode(signature)
    message = DOMAIN + signer.key_id.encode() + b"\x00" + bytes.fromhex(DIGEST)
    key.public_key().verify(raw, message)
    assert signer.verify(DIGEST, signature)
    assert signer.sign(DIGEST) == signature
    assert len(raw) == 64
    assert signer.public_key().algorithm == "Ed25519"
    assert signer.public_key().key_id == public_key_fingerprint(key.public_key())
    assert not verify_report_digest(DIGEST, signature, Ed25519PrivateKey.generate().public_key())
    for wrong in (
        bytes.fromhex(DIGEST),
        RESULT_DOMAIN + signer.key_id.encode() + b"\x00" + bytes.fromhex(DIGEST),
    ):
        assert not signer.verify(DIGEST, base64.b64encode(key.sign(wrong)).decode())


@pytest.mark.parametrize("bad", ["", "xyz", "A" * 64, None, True, 12, "a" * 63])
def test_digest_must_be_canonical_sha256(bad):
    signer = ReportSigner(Ed25519PrivateKey.generate())
    with pytest.raises(ValueError):
        signer.sign(bad)
    assert not signer.verify(bad, signer.sign(DIGEST))


@pytest.mark.parametrize("bad", ["", "MOCK-" + DIGEST, "!" * 88, "é" * 88, None, True, "A" * 89])
def test_bad_signature_is_false_not_exception(bad):
    signer = ReportSigner(Ed25519PrivateKey.generate())
    assert not signer.verify(DIGEST, bad)


def test_non_ed25519_keys_are_not_accepted():
    key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(ValueError):
        ReportSigner(key)
    assert not verify_report_digest(DIGEST, "A" * 88, key.public_key())


def test_real_report_bytes_tamper_repeat_and_persisted_signature(real_client):
    client = real_client
    jid, job = _run(client)
    endpoint = f"/v1/forensic/jobs/{jid}/report"
    response = client.get(endpoint)
    assert response.status_code == 200
    key = load_private_key(
        Path(client.app.state.vericlue.settings.report_signing_key_path)
    ).public_key()
    digest = hashlib.sha256(response.content).hexdigest()
    signature = response.headers["X-VeriClue-Signature"]
    assert response.headers["X-VeriClue-Signature-Algorithm"] == "Ed25519"
    assert response.headers["X-VeriClue-Key-Id"] == public_key_fingerprint(key)
    assert response.headers["X-VeriClue-Report-SHA256"] == digest
    assert response.headers["Cache-Control"] == "no-store"
    assert verify_report_digest(digest, signature, key)
    assert "Giới hạn" in response.text and job["file_sha256"] in response.text
    assert "không chứng nhận kết luận mô hình" in response.text
    modified = response.content.replace(b"<h1>", b"<H1>", 1)
    assert modified != response.content
    assert not verify_report_digest(hashlib.sha256(modified).hexdigest(), signature, key)
    repeated = client.get(endpoint)
    assert repeated.content == response.content
    assert repeated.headers["X-VeriClue-Signature"] == signature
    with client.app.state.vericlue.database.sessions() as db:
        row = db.get(ForensicJobRow, jid)
        assert row.signature == signature
    forged = client.post(
        "/v1/forensic/verify",
        json={
            "report_sha256": digest,
            "signature": "MOCK-" + digest,
        },
    )
    assert forged.json() == {"valid": False}


def test_key_and_verify_do_not_need_database_or_detector_initialization(monkeypatch):
    app = create_app()
    tokens = json.loads(app.state.vericlue.settings.staff_access_tokens.get_secret_value())
    headers = {"Authorization": "Bearer " + next(iter(tokens))}
    signer = app.state.vericlue.settings.report_signer

    def forbidden(*args, **kwargs):
        pytest.fail("Must not initialize DB/models or open a transaction")

    monkeypatch.setattr(app.state.vericlue, "initialize", forbidden)
    monkeypatch.setattr(app.state.vericlue.database, "sessions", forbidden)
    client = TestClient(app, headers=headers)
    try:
        assert client.get("/v1/forensic/signing-key").json() == signer.public_key().model_dump()
        valid = client.post(
            "/v1/forensic/verify", json={"report_sha256": DIGEST, "signature": signer.sign(DIGEST)}
        )
        assert valid.json() == {"valid": True}
        assert not app.state.vericlue._initialized
    finally:
        client.close()
        app.state.vericlue.orchestrator.close()
        app.state.vericlue.database.dispose()


@pytest.mark.parametrize(
    "configured", ["", "missing.pem", "wrong_curve", "public_only", "too_large"]
)
def test_unusable_report_key_is_503_without_fallback(monkeypatch, tmp_path, configured):
    path = tmp_path / "bad-key.pem"
    if configured in {"wrong_curve", "public_only", "too_large"}:
        if configured == "too_large":
            raw = b"x" * 4097
        elif configured == "public_only":
            raw = (
                Ed25519PrivateKey.generate()
                .public_key()
                .public_bytes(
                    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
                )
            )
        else:
            raw = ec.generate_private_key(ec.SECP256R1()).private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        path.write_bytes(raw)
        configured = str(path)
    monkeypatch.setenv("REPORT_SIGNING_KEY_PATH", configured)
    get_settings.cache_clear()
    app = create_app()
    tokens = json.loads(app.state.vericlue.settings.staff_access_tokens.get_secret_value())
    client = TestClient(app, headers={"Authorization": "Bearer " + next(iter(tokens))})
    try:
        assert client.get("/v1/forensic/signing-key").status_code == 503
        result = client.post(
            "/v1/forensic/verify", json={"report_sha256": DIGEST, "signature": "A" * 88}
        )
        assert result.status_code == 503
        assert result.json()["error_code"] == "report_signing_unavailable"
        assert not app.state.vericlue._initialized
    finally:
        client.close()
        app.state.vericlue.orchestrator.close()
        app.state.vericlue.database.dispose()


def test_real_job_without_key_cannot_return_unsigned_or_mock_report(real_client, monkeypatch):
    jid, _ = _run(real_client)
    root = real_client.app.state.vericlue
    monkeypatch.setattr(root.settings, "report_signing_key_path", None)
    root.settings.__dict__.pop("report_signer", None)
    response = real_client.get(f"/v1/forensic/jobs/{jid}/report")
    assert response.status_code == 503
    assert response.json()["error_code"] == "report_signing_unavailable"
    with root.database.sessions() as db:
        row = db.get(ForensicJobRow, jid)
        assert row.signature is None and row.report_path is None


def test_verification_does_not_accept_supplied_keys_or_extra_claims(client):
    response = client.post(
        "/v1/forensic/verify",
        json={
            "report_sha256": DIGEST,
            "signature": "A" * 88,
            "public_key": "attacker-key",
        },
    )
    assert response.status_code == 422
    assert (
        client.post(
            "/v1/forensic/verify", json={"report_sha256": DIGEST, "signature": "A" * 161}
        ).status_code
        == 422
    )


def test_mock_report_remains_explicit_and_never_verifies_as_signed(client):
    created = client.post("/v1/forensic/jobs", files={"file": ("sample.wav", b"mock", "audio/wav")})
    report = client.get(f"/v1/forensic/jobs/{created.json()['job_id']}/report")
    assert report.status_code == 200
    assert "bản mock" in report.text and "Giới hạn" in report.text
    assert report.headers["X-VeriClue-Signature-Algorithm"] == "MOCK"
    assert "X-VeriClue-Key-Id" not in report.headers
    signature = report.headers["X-VeriClue-Signature"]
    assert client.post(
        "/v1/forensic/verify",
        json={
            "report_sha256": report.headers["X-VeriClue-Report-SHA256"],
            "signature": signature,
        },
    ).json() == {"valid": False}
