"""Build a signed export from durable server results, without accepting client report data."""

import hashlib
from datetime import UTC

from vericlue_api import __version__
from vericlue_api.core.errors import ApiError
from vericlue_api.core.pdf_bundle import make_archive
from vericlue_api.db.models import ForensicJobRow
from vericlue_api.schemas.forensic import PdfReportManifest
from vericlue_api.services.forensic_service import LIMITATIONS_VI, ForensicStore
from vericlue_api.services.pdf_renderer import PdfRenderer


def export_pdf_bundle(store: ForensicStore, renderer: PdfRenderer, job_id: str) -> bytes:
    """Only done real jobs; PDF/JSON/signature share one snapshot and one ZIP response."""
    job = store.report_job(job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "Không tìm thấy job giám định.")
    if job.status != "done":
        raise ApiError(409, "job_not_ready", "Job chưa hoàn tất nên chưa xuất được báo cáo.")
    row = store.db.get(ForensicJobRow, job_id)
    if row.payload.get("mode") != "real":
        raise ApiError(409, "report_not_eligible", "Bản mô phỏng không được cấp gói báo cáo đã ký.")
    signer = store.report_signer()
    try:
        created = (
            row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
        )
        render_payload = {
            **row.payload,
            "pdf_report_context": {
                "job_created_at": created.isoformat(),
                "tool_version": __version__,
            },
        }
        html = store._report_real(job, render_payload, signer.key_id, pdf_bundle=True)
        html = html.replace("\u2013", "-").replace("\u2014", "-").replace("\u2011", "-")
        pdf = renderer.render(html)
        manifest = PdfReportManifest(
            version=1,
            protocol="vericlue-forensic-pdf-bundle-v1",
            algorithm="Ed25519",
            data_mode="real",
            key_id=signer.key_id,
            job=job,
            filename=row.payload.get("filename", ""),
            job_created_at=created,
            tool_version=__version__,
            model_versions=row.payload.get("model_versions", {}),
            pdf_sha256=hashlib.sha256(pdf).hexdigest(),
            limitations=list(LIMITATIONS_VI),
        )
        raw, signature = signer.sign_bundle(manifest)
        return make_archive(pdf, raw, signature)
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(
            503, "report_export_unavailable", "Chưa thể xuất gói báo cáo lúc này."
        ) from exc
