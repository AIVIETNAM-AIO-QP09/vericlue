"""Signed artifact integrity with real keys and synthetic PDF bytes, no ML claims."""

import base64
import hashlib
import io
import json
import struct
import subprocess
import zipfile
from datetime import UTC, datetime

import pytest
from contract_utils import validate
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_forensic_real import _run
from test_forensic_real import real_client as real_client

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.pdf_bundle import (
    DOMAIN,
    MEMBERS,
    canonical_manifest,
    make_archive,
    signing_message,
    verify_archive,
    verify_parts,
)
from vericlue_api.core.report_signing import ReportSigner
from vericlue_api.schemas.forensic import ForensicJob, PdfReportManifest
from vericlue_api.services import pdf_renderer
from vericlue_api.services.pdf_renderer import PdfRenderer, worker_environment

PDF = b"%PDF-1.4\nSynthetic integrity test bytes, not a renderable report.\n%%EOF"


@pytest.fixture
def artifact():
    private = Ed25519PrivateKey.generate()
    signer = ReportSigner(private)
    manifest = PdfReportManifest(
        version=1,
        protocol="vericlue-forensic-pdf-bundle-v1",
        algorithm="Ed25519",
        data_mode="real",
        key_id=signer.key_id,
        job=ForensicJob(job_id="job_synthetic", status="done", file_sha256="a" * 64, segments=[]),
        filename="Mẫu tổng hợp.wav",
        job_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tool_version="test",
        model_versions={"voice_spoof": "synthetic-test-only"},
        pdf_sha256=hashlib.sha256(PDF).hexdigest(),
        limitations=["Dữ liệu tổng hợp, không đánh giá mô hình."],
    )
    raw, signature = signer.sign_bundle(manifest)
    return signer, private.public_key(), manifest, raw, signature


def test_bundle_round_trip_and_contract(artifact):
    signer, key, manifest, raw, signature = artifact
    validate(manifest.model_dump(mode="json", exclude_none=True), "forensic", "PdfReportManifest")
    assert raw == canonical_manifest(manifest)
    key.verify(base64.b64decode(signature), DOMAIN + signer.key_id.encode() + b"\x00" + raw)
    archive = make_archive(PDF, raw, signature)
    verified = verify_archive(archive, key, expected_job_id="job_synthetic")
    assert verified == manifest
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert set(bundle.namelist()) == set(MEMBERS)
        assert all(member.compress_type == zipfile.ZIP_STORED for member in bundle.infolist())


@pytest.mark.parametrize(
    "fault", ["pdf", "json", "signature", "key", "job", "html-signature", "missing-signature"]
)
def test_changed_or_wrong_context_is_rejected(artifact, fault):
    signer, key, _, raw, signature = artifact
    pdf = PDF
    job = "job_synthetic"
    if fault == "pdf":
        pdf += b" "
    elif fault == "json":
        raw = raw.replace(b"job_synthetic", b"job_changed__")
    elif fault == "signature":
        signature = base64.b64encode(b"x" * 64).decode()
    elif fault == "key":
        key = Ed25519PrivateKey.generate().public_key()
    elif fault == "job":
        job = "job_other"
    elif fault == "html-signature":
        signature = signer.sign(hashlib.sha256(PDF).hexdigest())
    elif fault == "missing-signature":
        signature = "MOCK-" + "a" * 64
    with pytest.raises(ValueError, match="Bundle not verified"):
        verify_parts(pdf, raw, signature, key, expected_job_id=job)


@pytest.mark.parametrize(
    "fault",
    [
        "whitespace",
        "duplicate",
        "unknown",
        "wrong-key-id",
        "empty-limits",
        "failed",
        "true-version",
    ],
)
def test_even_signed_noncanonical_or_invalid_manifests_fail(artifact, fault):
    signer, key, _, raw, _ = artifact
    data = json.loads(raw)
    if fault == "whitespace":
        raw = json.dumps(data).encode()
    elif fault == "duplicate":
        raw = b'{"version":1,' + raw[1:]
    else:
        if fault == "unknown":
            data["public_key"] = "attacker"
        elif fault == "wrong-key-id":
            data["key_id"] = "b" * 64
        elif fault == "empty-limits":
            data["limitations"] = []
        elif fault == "failed":
            data["job"]["status"] = "failed"
        elif fault == "true-version":
            data["version"] = True
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    signature = base64.b64encode(signer._key.sign(signing_message(raw, signer.key_id))).decode()
    with pytest.raises(ValueError):
        verify_parts(PDF, raw, signature, key)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "duplicate",
        "traversal",
        "compressed",
        "symlink",
        "directory-count",
        "directory-size",
    ],
)
def test_unsafe_archive_layouts_fail_before_extraction(artifact, fault):
    _, key, _, raw, signature = artifact
    output = io.BytesIO()
    members = {"report.pdf": PDF, "report.json": raw, "report.sig": signature.encode()}
    if fault == "missing":
        members.pop("report.pdf")
    if fault == "extra":
        members["other.txt"] = b"extra"
    if fault == "traversal":
        members["../report.pdf"] = members.pop("report.pdf")
    compression = zipfile.ZIP_DEFLATED if fault == "compressed" else zipfile.ZIP_STORED
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, value in members.items():
            if fault == "symlink" and name == "report.pdf":
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = 0o120777 << 16
                archive.writestr(info, value)
            else:
                archive.writestr(name, value)
        if fault == "duplicate":
            with pytest.warns(UserWarning):
                archive.writestr("report.pdf", PDF)
    zipped = bytearray(output.getvalue())
    if fault == "directory-count":
        struct.pack_into("<H", zipped, len(zipped) - 12, 65535)
    if fault == "directory-size":
        struct.pack_into("<L", zipped, len(zipped) - 10, 65536)
    with pytest.raises(ValueError, match="Bundle not verified"):
        verify_archive(bytes(zipped), key)


def test_pdf_export_endpoint_and_eligibility(real_client, monkeypatch):
    client = real_client
    jid, original = _run(client)
    seen = []

    def render(self, html):
        seen.append(html)
        return PDF

    monkeypatch.setattr(PdfRenderer, "render", render)
    response = client.get(f"/v1/forensic/jobs/{jid}/report-bundle")
    assert response.status_code == 200, response.text
    assert response.headers["Content-Type"] == "application/zip"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Content-Disposition"].endswith(f'"{jid}-report.zip"')
    signer = client.app.state.vericlue.settings.report_signer
    manifest = verify_archive(response.content, signer._key.public_key(), expected_job_id=jid)
    assert manifest.job.file_sha256 == original["file_sha256"]
    assert manifest.job.verdict == original["verdict"]
    assert manifest.limitations and "Giới hạn" in seen[0] and "BẢN THỬ NGHIỆM" in seen[0]
    assert "JSON và hash PDF" in seen[0]
    assert "Thời điểm tạo job:" in seen[0] and "Phiên bản VeriClue:" in seen[0]
    client.headers.clear()
    assert client.get(f"/v1/forensic/jobs/{jid}/report-bundle").status_code == 401


def test_mock_and_unknown_jobs_do_not_start_renderer(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Must not render mock/unknown jobs")

    monkeypatch.setattr(PdfRenderer, "render", forbidden)
    created = client.post(
        "/v1/forensic/jobs", files={"file": ("a.wav", b"mock", "audio/wav")}
    ).json()
    assert client.get(f"/v1/forensic/jobs/{created['job_id']}/report-bundle").status_code == 409
    assert client.get("/v1/forensic/jobs/missing/report-bundle").status_code == 404


def test_missing_runtime_is_503_and_existing_html_still_works(real_client):
    jid, _ = _run(real_client)
    response = real_client.get(f"/v1/forensic/jobs/{jid}/report-bundle")
    assert response.status_code == 503 and response.json()["error_code"] == "pdf_unavailable"
    assert real_client.get(f"/v1/forensic/jobs/{jid}/report").status_code == 200


def test_worker_environment_does_not_receive_api_secrets(monkeypatch):
    for name in (
        "SESSION_MASTER_KEY",
        "STAFF_ACCESS_TOKENS",
        "NODE_OPTIONS",
        "HTTPS_PROXY",
        "SESSION_SIGNING_SECRET",
    ):
        monkeypatch.setenv(name, "synthetic-secret-do-not-forward")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "synthetic-browser-path")
    env = worker_environment()
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == "synthetic-browser-path"
    assert "synthetic-secret-do-not-forward" not in env.values()


@pytest.fixture
def configured_renderer(tmp_path):
    node = tmp_path / "node.exe"
    node.write_bytes(b"synthetic runtime path, never executed")
    module = tmp_path / "playwright"
    module.mkdir()
    (module / "package.json").write_text("{}")
    return PdfRenderer(
        Settings(
            _env_file=None,
            forensic_pdf_node=str(node),
            forensic_pdf_playwright_dir=str(module),
            forensic_pdf_timeout_seconds=1,
        )
    )


def test_renderer_busy_rejects_without_starting_another_process(configured_renderer, monkeypatch):
    monkeypatch.setattr(
        pdf_renderer.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("Must not start a second process"),
    )
    assert pdf_renderer._SLOT.acquire(blocking=False)
    try:
        with pytest.raises(ApiError) as error:
            configured_renderer.render("<p>Synthetic</p>")
        assert error.value.error_code == "pdf_busy"
    finally:
        pdf_renderer._SLOT.release()


def test_timeout_stops_own_worker_and_releases_slot(configured_renderer, monkeypatch):
    class Worker:
        returncode = None
        calls = 0

        def communicate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("synthetic worker", 1)
            return b"", b"synthetic private document must not escape"

        def poll(self):
            return self.returncode

    worker = Worker()
    stopped = []
    monkeypatch.setattr(pdf_renderer.subprocess, "Popen", lambda *args, **kwargs: worker)

    def stop(process):
        assert process is worker
        stopped.append(process)
        process.returncode = -9

    monkeypatch.setattr(pdf_renderer, "_stop_tree", stop)
    with pytest.raises(ApiError) as error:
        configured_renderer.render("<p>synthetic private document</p>")
    assert error.value.error_code == "pdf_unavailable" and stopped == [worker]
    assert "private" not in error.value.message
    assert pdf_renderer._SLOT.acquire(blocking=False)
    pdf_renderer._SLOT.release()


def test_bundle_missing_key_does_not_render_or_issue(real_client, monkeypatch):
    jid, _ = _run(real_client)
    settings = real_client.app.state.vericlue.settings
    monkeypatch.setattr(settings, "report_signing_key_path", None)
    settings.__dict__.pop("report_signer", None)
    monkeypatch.setattr(
        PdfRenderer, "render", lambda *args: pytest.fail("Must not render without signing key")
    )
    response = real_client.get(f"/v1/forensic/jobs/{jid}/report-bundle")
    assert (
        response.status_code == 503
        and response.json()["error_code"] == "report_signing_unavailable"
    )
