"""CLI validates signed bytes and expected job without extracting or rendering ZIP."""

import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vericlue_api.core.pdf_bundle import make_archive
from vericlue_api.core.report_signing import ReportSigner
from vericlue_api.schemas.forensic import ForensicJob, PdfReportManifest

spec = importlib.util.spec_from_file_location(
    "verify_pdf_bundle", Path(__file__).resolve().parents[1] / "verify_pdf_bundle.py"
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture
def files(tmp_path):
    key = Ed25519PrivateKey.generate()
    signer = ReportSigner(key)
    pdf = b"%PDF-1.4\nSynthetic test bytes\n%%EOF"
    manifest = PdfReportManifest(
        version=1,
        protocol="vericlue-forensic-pdf-bundle-v1",
        algorithm="Ed25519",
        data_mode="real",
        key_id=signer.key_id,
        job=ForensicJob(job_id="job_synthetic", status="done", file_sha256="a" * 64, segments=[]),
        filename="sample.wav",
        job_created_at=datetime.now(UTC),
        tool_version="test",
        model_versions={},
        pdf_sha256=hashlib.sha256(pdf).hexdigest(),
        limitations=["Synthetic test only."],
    )
    raw, signature = signer.sign_bundle(manifest)
    bundle = tmp_path / "report.zip"
    bundle.write_bytes(make_archive(pdf, raw, signature))
    public = tmp_path / "public.pem"
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return bundle, public


def test_cli_success(files, capsys):
    bundle, public = files
    assert (
        cli.main(
            [
                "--bundle",
                str(bundle),
                "--public-key",
                str(public),
                "--expected-job-id",
                "job_synthetic",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is True and result["job_id"] == "job_synthetic"


@pytest.mark.parametrize("fault", ["key", "job", "file", "size"])
def test_cli_failure_is_generic(files, capsys, monkeypatch, fault):
    bundle, public = files
    expected = "job_synthetic"
    if fault == "key":
        public.write_bytes(
            Ed25519PrivateKey.generate()
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
    elif fault == "job":
        expected = "job_other"
    elif fault == "file":
        bundle.write_bytes(b"not-a-zip")
    elif fault == "size":
        monkeypatch.setattr(cli, "MAX_ZIP_BYTES", 1)
    assert (
        cli.main(
            ["--bundle", str(bundle), "--public-key", str(public), "--expected-job-id", expected]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {"valid": False}
