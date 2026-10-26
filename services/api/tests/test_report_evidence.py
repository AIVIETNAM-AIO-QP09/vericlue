"""Synthetic source/PNG only; extraction safety and signed presentation, not ML evidence."""

import hashlib
import io
import os
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from test_forensic_real import _run
from test_forensic_real import real_client as real_client

from vericlue_api.core.config import Settings
from vericlue_api.core.pdf_bundle import verify_archive
from vericlue_api.core.report_signing import verify_report_digest
from vericlue_api.schemas.forensic import ForensicJob, ForensicMedia, SuspectInterval
from vericlue_api.services import report_evidence
from vericlue_api.services.pdf_renderer import PdfRenderer
from vericlue_api.services.report_evidence import (
    MAX_INTERVALS,
    MAX_PNG,
    Illustration,
    ReportEvidence,
    ReportEvidenceBuilder,
    _png,
)


@pytest.fixture
def png():
    output = io.BytesIO()
    Image.new("RGB", (64, 36), "#28577d").save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def sample(tmp_path):
    root = tmp_path / "media"
    source = root / "forensic/job_synthetic/source.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"synthetic original file")
    tool = tmp_path / "ffmpeg.exe"
    tool.write_bytes(b"synthetic path, never executed in unit tests")
    settings = Settings(
        _env_file=None,
        media_dir=str(root),
        forensic_report_evidence=True,
        forensic_report_ffmpeg=str(tool),
    )
    job = ForensicJob(
        job_id="job_synthetic",
        status="done",
        file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        segments=[],
        media=ForensicMedia(kind="video"),
        suspect_intervals=[SuspectInterval(t_start=2, t_end=10, modules=["face_deepfake"])],
    )
    row = SimpleNamespace(
        job_id=job.job_id,
        file_sha256=job.file_sha256,
        source_path=str(source),
        payload={"mode": "real"},
    )
    return ReportEvidenceBuilder(settings), job, row, source


def fake_tool(monkeypatch, png, calls):
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            returncode=0, stdout=b"ffmpeg synthetic version\n" if args[1:] == ["-version"] else png
        )

    monkeypatch.setattr(report_evidence.subprocess, "run", run)


def test_hash_checked_snapshot_only_local_formats_and_scrubbed_environment(
    sample, png, monkeypatch
):
    builder, job, row, source = sample
    calls = []
    original = source.read_bytes()

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[1:] == ["-version"]:
            # Subsequent decodes must use the verified snapshot, not the live file.
            source.write_bytes(b"synthetic source changed after snapshot")
            return SimpleNamespace(returncode=0, stdout=b"ffmpeg synthetic version\n")
        snapshot = Path(args[args.index("-i") + 1])
        assert snapshot != source and snapshot.read_bytes() == original
        return SimpleNamespace(returncode=0, stdout=png)

    monkeypatch.setenv("SESSION_MASTER_KEY", "synthetic-secret")
    monkeypatch.setenv("FFREPORT", "file=must-not-write.log")
    monkeypatch.setattr(report_evidence.subprocess, "run", run)
    evidence = builder.build(job, row)
    assert len(evidence.figures) == 2 and not evidence.notes
    assert "2-5 s" in evidence.figures[1].caption
    assert "3.5 s" in evidence.figures[0].caption
    for args, kwargs in calls:
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert 0 < kwargs["timeout"] <= 4
        assert "SESSION_MASTER_KEY" not in kwargs["env"] and "FFREPORT" not in kwargs["env"]
        assert "shell" not in kwargs
        if "-i" in args:
            assert args[args.index("-protocol_whitelist") + 1] == "file,pipe"
            formats = args[args.index("-format_whitelist") + 1].split(",")
            assert not set(formats) & {"hls", "concat", "dash", "image2"}
            assert not Path(args[args.index("-i") + 1]).exists()  # temp snapshot removed


@pytest.mark.parametrize("fault", ["changed", "row-hash", "missing", "outside", "job-id", "large"])
def test_ineligible_source_never_starts_ffmpeg(sample, monkeypatch, fault):
    builder, job, row, source = sample
    if fault == "changed":
        source.write_bytes(b"changed")
    elif fault == "row-hash":
        row.file_sha256 = "f" * 64
    elif fault == "missing":
        source.unlink()
    elif fault == "outside":
        row.source_path = str(source.parent.parent / source.name)
    elif fault == "job-id":
        job.job_id = "../other"
    else:
        monkeypatch.setattr(report_evidence, "MAX_SOURCE", 1)
    monkeypatch.setattr(report_evidence.subprocess, "run", lambda *a, **k: pytest.fail("No decode"))
    result = builder.build(job, row)
    assert not result.figures and result.notes
    assert str(source) not in result.html()


def test_disabled_missing_runtime_empty_intervals_and_mock_never_decode(sample, monkeypatch):
    builder, job, row, _ = sample
    monkeypatch.setattr(report_evidence.subprocess, "run", lambda *a, **k: pytest.fail("No decode"))
    builder.settings.forensic_report_evidence = False
    assert builder.build(job, row) is None
    builder.settings.forensic_report_evidence = True
    builder.settings.forensic_report_ffmpeg = None
    assert not builder.build(job, row).figures
    row.payload["mode"] = "mock"
    assert not builder.build(job, row).figures
    row.payload["mode"] = "real"
    job.suspect_intervals = []
    assert "Không có khoảng" in builder.build(job, row).html()


def test_budget_busy_and_timeouts_omit_figures_and_release_slot(sample, png, monkeypatch):
    builder, job, row, _ = sample
    with report_evidence._SLOT:
        assert not builder.build(job, row).figures

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic-ffmpeg", 4)

    monkeypatch.setattr(report_evidence.subprocess, "run", timeout)
    assert not builder.build(job, row).figures
    fake_tool(monkeypatch, png, [])
    assert len(builder.build(job, row).figures) == 2
    monkeypatch.setattr(report_evidence, "TOTAL_SECONDS", 0)
    assert not builder.build(job, row).figures


def test_cap_intervals_audio_only_and_invalid_windows(sample, png, monkeypatch):
    builder, job, row, _ = sample
    calls = []
    fake_tool(monkeypatch, png, calls)
    job.media.kind = "audio"
    job.suspect_intervals *= MAX_INTERVALS + 1
    evidence = builder.build(job, row)
    assert len(evidence.figures) == MAX_INTERVALS
    assert len(calls) == MAX_INTERVALS + 1
    assert evidence.notes
    job.suspect_intervals = [SuspectInterval(t_start=3, t_end=1)]
    assert not builder.build(job, row).figures


@pytest.mark.parametrize("fault", ["magic", "crc", "truncated", "oversize", "dimensions"])
def test_invalid_png_is_not_embedded(png, fault):
    if fault == "magic":
        png = b"<svg>synthetic</svg>"
    elif fault == "crc":
        png = png[:40] + bytes([png[40] ^ 1]) + png[41:]
    elif fault == "truncated":
        png = png[:-12]
    elif fault == "oversize":
        png += b"x" * MAX_PNG
    else:
        png = png[:16] + struct.pack(">II", 2000, 500) + png[24:]
    with pytest.raises(ValueError):
        _png(png)


def test_illustration_text_is_escaped(png):
    evidence = ReportEvidence(
        (Illustration('<script>"</script>', png),), ("<b>note</b>",), '<img src="x">'
    )
    html = evidence.html()
    assert "<script>" not in html and '<img src="x">' not in html and "<b>note</b>" not in html
    assert "data:image/png;base64," in html


def test_html_signature_and_pdf_hash_cover_generated_illustrations(real_client, png, monkeypatch):
    from vericlue_api.services.forensic_service import ForensicStore

    evidence = ReportEvidence((Illustration("Hình tổng hợp, không phải vật chứng thật", png),))
    monkeypatch.setattr(ForensicStore, "report_evidence", lambda *a: evidence)
    jid, _ = _run(real_client)
    root = real_client.app.state.vericlue
    signer = root.settings.report_signer
    html = real_client.get(f"/v1/forensic/jobs/{jid}/report")
    assert html.status_code == 200 and "data:image/png;base64," in html.text
    signature = html.headers["X-VeriClue-Signature"]
    assert verify_report_digest(
        hashlib.sha256(html.content).hexdigest(), signature, signer._key.public_key()
    )
    changed = html.content.replace(b"data:image/png", b"data:image/bmp")
    assert not verify_report_digest(
        hashlib.sha256(changed).hexdigest(), signature, signer._key.public_key()
    )
    seen = []

    def render(self, markup):
        seen.append(markup)
        return b"%PDF-1.4\nSynthetic integrity bytes\n%%EOF"

    monkeypatch.setattr(PdfRenderer, "render", render)
    response = real_client.get(f"/v1/forensic/jobs/{jid}/report-bundle")
    assert response.status_code == 200, response.text
    verified = verify_archive(response.content, signer._key.public_key(), expected_job_id=jid)
    assert verified.job.job_id == jid and "data:image/png;base64," in seen[0]


def test_real_ffmpeg_extracts_synthetic_video_and_spectrogram(sample):
    """Opt-in native integration; CI supplies FFmpeg, never faces/voices/models."""
    tool = os.environ.get("TEST_FFMPEG_BINARY")
    if not tool:
        pytest.skip("TEST_FFMPEG_BINARY enables real FFmpeg integration")
    builder, job, row, source = sample
    builder.settings.forensic_report_ffmpeg = tool
    subprocess.run(
        [
            tool,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000",
            "-t",
            "6",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=20,
        **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
    )
    original = source.read_bytes()
    job.file_sha256 = row.file_sha256 = hashlib.sha256(original).hexdigest()
    evidence = builder.build(job, row)
    assert len(evidence.figures) == 2, evidence.notes
    assert not evidence.notes and evidence.runtime.startswith("ffmpeg version")
    for figure in evidence.figures:
        assert _png(figure.png) == figure.png
        with Image.open(io.BytesIO(figure.png)) as image:
            image.verify()
    assert source.read_bytes() == original


def test_real_ffmpeg_refuses_playlist_network_resource(sample):
    """A staff upload containing a playlist must not turn into a network fetch."""
    import http.server
    import threading

    tool = os.environ.get("TEST_FFMPEG_BINARY")
    if not tool:
        pytest.skip("TEST_FFMPEG_BINARY enables real FFmpeg integration")
    builder, job, row, source = sample
    builder.settings.forensic_report_ffmpeg = tool
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *_args):
            pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.1), daemon=True
        )
        thread.start()
        try:
            source.write_text(
                "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:5\n#EXTINF:5,\n"
                f"http://127.0.0.1:{server.server_port}/must-not-fetch.ts\n#EXT-X-ENDLIST\n",
                encoding="ascii",
            )
            job.file_sha256 = row.file_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
            evidence = builder.build(job, row)
            assert not evidence.figures and evidence.notes
            assert requests == []
        finally:
            server.shutdown()
            thread.join(timeout=2)
