"""Giám định: lưu job, tiến độ và báo cáo.

- `USE_MOCK_MODELS=true`: giữ bản mock cũ (test và demo); chạy đồng bộ, kết quả giả lập.
- Còn lại (`false`, `mixed`): job vào hàng `queued`, tác vụ nền (`forensic_runner.py`) chia đoạn 3 giây
  chồng lấn 50% và chạy bộ phát hiện THẬT; `GET /jobs/{id}` trả tiến độ. Module chưa có mô hình thật
  hiện là `unavailable`, không bao giờ được giả lập; thiếu bước bắt buộc → `inconclusive`.

PLAT-06 ký HTML của job real bằng Ed25519, mock không được xác minh là chữ ký thật.
Đây chưa phải gói PDF/JSON ENFSI của FOR-04. SHA-256 tính trên byte gốc trước mọi bước
đọc/chuyển mã (AGENTS.md, ADR-0008).
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.errors import ApiError
from vericlue_api.core.report_signing import ReportSigner
from vericlue_api.db.models import ForensicJobRow, ForensicSegmentRow
from vericlue_api.schemas.forensic import (
    ForensicJob,
    ForensicSegment,
    ReviewAuditAnchor,
    SegmentSignal,
    Verdict,
)
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.report_evidence import ReportEvidence
from vericlue_api.services.review_audit_link import ReviewAuditLinker
from vericlue_api.services.storage import save_generated, save_upload
from vericlue_ml.common.result import Module, ModuleResult, Status

FORENSIC_MODULES = (Module.FACE_DEEPFAKE, Module.VOICE_SPOOF, Module.LIPSYNC, Module.PROVENANCE)
SEGMENT_SECONDS = 5.0  # chỉ cho bản mock
SEGMENTS = 2  # chỉ cho bản mock
MOCK_SIGNATURE_PREFIX = "MOCK-"  # Checksum mô phỏng, không phải chữ ký được tin cậy.

_STATUS_LABELS_VI = {
    "not_applicable": "không áp dụng",
    "unavailable": "chưa chạy",
    "error": "lỗi",
    "degraded": "đầu vào kém",
}
_VERDICT_LABELS_VI = {
    "authentic": "không phát hiện dấu hiệu làm giả (không phải chứng nhận là thật)",
    "suspect": "có dấu hiệu nghi làm giả",
    "inconclusive": "chưa thể kết luận",
}
LIMITATIONS_VI = (
    "Công cụ hỗ trợ, không thay thế giám định tư pháp.",
    "Điểm xác suất tạm thời: bộ hiệu chỉnh là identity (ADR-0012), chưa có calibrator riêng cho giám định "
    "và chưa có tỷ số khả năng/thang lời ENFSI (FOR-04).",
    "Không phát hiện dấu hiệu không có nghĩa là thật; mô hình có thể bỏ sót kỹ thuật làm giả mới.",
    "Quét nguồn gốc là bằng chứng một chiều: thủy vân/C2PA có thì cho biết công cụ, không có thì không kết luận.",
    "Video đã nén nhiều lần có thể làm sai lệch điểm; ngưỡng là giá trị tạm chờ ROUT-03.",
    "Ngưỡng eKYC áp cho từng đoạn nên video dài dễ báo nghi ngờ nhầm.",
)


def _signal(r: ModuleResult) -> SegmentSignal:
    return SegmentSignal(
        module=str(r.module), applicable=r.status == Status.OK, prob_attack=r.prob_attack
    )


class ForensicStore:
    def __init__(
        self,
        b: float,
        a: float,
        db: DBSession,
        media_dir: str,
        *,
        runner: Callable = run_detectors,
        mock: bool = True,
        report_signer: Callable[[], ReportSigner] | None = None,
        review_links: ReviewAuditLinker | None = None,
        evidence_builder: Callable[[ForensicJob, ForensicJobRow], ReportEvidence | None]
        | None = None,
    ) -> None:
        self._b, self._a = b, a
        self._run = runner
        self.mock = mock
        self.db, self.media_dir = db, media_dir
        self._report_signer = report_signer
        self._review_links = review_links
        self._evidence_builder = evidence_builder

    # --- tạo job ------------------------------------------------------------
    def create(
        self, data: bytes, filename: str | None, scenario: str, *, review_case_id: str | None = None
    ) -> ForensicJob:
        anchor = None
        if review_case_id is not None:
            if self.mock:
                raise ApiError(
                    409,
                    "review_link_unavailable",
                    "Bản mô phỏng không cấp liên kết vật chứng đã kiểm.",
                )
            if self._review_links is None:
                raise ApiError(503, "review_link_unavailable", "Chưa thể liên kết hồ sơ.")
            anchor = self._review_links.bind(review_case_id, data)
        if not self.mock:
            return self._create_queued(data, filename, review_audit=anchor)
        return self._create_mock(data, filename, scenario)

    def _create_queued(
        self, data: bytes, filename: str | None, *, review_audit: ReviewAuditAnchor | None = None
    ) -> ForensicJob:
        """Tiếp nhận: hash TRÊN BYTE GỐC, lưu file nguyên vẹn, xếp hàng. Chưa đọc/giải mã gì cả."""
        job = ForensicJob(
            job_id=f"job_{secrets.token_hex(6)}",
            status="queued",
            file_sha256=hashlib.sha256(data).hexdigest(),
            verdict=None,
            segments=[],
            review_audit=review_audit,
        )
        path = save_upload(self.media_dir, "forensic/" + job.job_id, "source", filename, data)
        self.db.add(
            ForensicJobRow(
                job_id=job.job_id,
                file_sha256=job.file_sha256,
                status=job.status,
                verdict=None,
                source_path=str(path),
                payload={
                    "mode": "real",
                    "job": job.model_dump(mode="json"),
                    "filename": filename or "",
                },
            )
        )
        self.db.flush()
        return job

    def _create_mock(self, data: bytes, filename: str | None, scenario: str) -> ForensicJob:
        results = self._run(FORENSIC_MODULES, session_id=None, scenario=scenario)
        segments = [
            ForensicSegment(
                t_start=i * SEGMENT_SECONDS,
                t_end=(i + 1) * SEGMENT_SECONDS,
                signals=[_signal(r) for r in results.values()],
            )
            for i in range(SEGMENTS)
        ]
        probs = [
            r.prob_attack
            for r in results.values()
            if r.status == Status.OK and r.prob_attack is not None
        ]
        worst = max(probs, default=None)
        verdict: Verdict
        if worst is None or any(r.status != Status.OK for r in results.values()):
            verdict = "inconclusive"
        elif worst >= self._a:
            verdict = "suspect"
        elif worst >= self._b:
            verdict = "inconclusive"
        else:
            verdict = "authentic"
        job = ForensicJob(
            job_id=f"job_{secrets.token_hex(6)}",
            status="done",
            file_sha256=hashlib.sha256(data).hexdigest(),  # trên byte gốc
            verdict=verdict,
            segments=segments,
        )
        path = save_upload(self.media_dir, "forensic/" + job.job_id, "source", filename, data)
        self.db.add(
            ForensicJobRow(
                job_id=job.job_id,
                file_sha256=job.file_sha256,
                status=job.status,
                verdict=job.verdict,
                source_path=str(path),
                payload={
                    "job": job.model_dump(mode="json"),
                    "filename": filename or "",
                    "module_results": {str(m): r.to_contract() for m, r in results.items()},
                },
            )
        )
        self.db.flush()
        for segment in job.segments:
            self.db.add(
                ForensicSegmentRow(
                    job_id=job.job_id,
                    t_start=segment.t_start,
                    t_end=segment.t_end,
                    signals=[s.model_dump(mode="json") for s in segment.signals],
                )
            )
        return job

    # --- vòng đời job thật (tác vụ nền gọi) ------------------------------------
    def _row(self, job_id: str) -> ForensicJobRow | None:
        return self.db.get(ForensicJobRow, job_id)

    def source_path(self, job_id: str) -> str | None:
        row = self._row(job_id)
        return row.source_path if row else None

    def _update_job(self, row: ForensicJobRow, **fields: Any) -> ForensicJob:
        data = dict(row.payload["job"])
        data.update(fields)
        job = ForensicJob.model_validate(data)
        row.status = job.status
        row.verdict = job.verdict
        # gán lại cả dict để SQLAlchemy ghi nhận thay đổi JSON
        row.payload = {**row.payload, "job": job.model_dump(mode="json")}
        self.db.flush()
        return job

    def mark_running(self, job_id: str) -> None:
        row = self._row(job_id)
        if row is not None and row.status == "queued":
            self._update_job(
                row,
                status="running",
                progress={"stage": "probe", "segments_done": 0, "segments_total": 0},
            )

    def set_progress(self, job_id: str, stage: str, done: int, total: int) -> None:
        row = self._row(job_id)
        if row is not None and row.status == "running":
            self._update_job(
                row, progress={"stage": stage, "segments_done": done, "segments_total": total}
            )

    def complete(self, job_id: str, analysis: Any, media: dict[str, Any]) -> ForensicJob | None:
        """Ghi kết quả của `ForensicPipeline.run` (ForensicAnalysis)."""
        row = self._row(job_id)
        if row is None:
            return None
        segments = [
            {
                "t_start": seg.t_start,
                "t_end": seg.t_end,
                "signals": [
                    {
                        "module": s.module,
                        "applicable": s.applicable,
                        "prob_attack": s.prob_attack,
                        "status": s.status,
                        "reason": s.reason,
                    }
                    for s in seg.signals
                ],
            }
            for seg in analysis.segments
        ]
        total = len(segments)
        job = self._update_job(
            row,
            status="done",
            verdict=analysis.verdict,
            verdict_reason=analysis.verdict_reason,
            segments=segments,
            media=media,
            suspect_intervals=analysis.suspect_intervals,
            unavailable_modules=analysis.unavailable_modules,
            provenance=analysis.provenance,
            progress={"stage": "finalize", "segments_done": total, "segments_total": total},
            error=None,
        )
        row.payload = {**row.payload, "model_versions": analysis.model_versions}
        for segment in job.segments:
            self.db.add(
                ForensicSegmentRow(
                    job_id=job_id,
                    t_start=segment.t_start,
                    t_end=segment.t_end,
                    signals=[s.model_dump(mode="json") for s in segment.signals],
                )
            )
        self.db.flush()
        return job

    def fail_interrupted(self) -> int:
        """Khởi động lại: job thật còn `queued`/`running` đã mất tác vụ nền → `failed` (không treo mãi)."""
        rows = self.db.scalars(
            select(ForensicJobRow).where(ForensicJobRow.status.in_(("queued", "running")))
        ).all()
        count = 0
        for row in rows:
            if row.payload.get("mode") != "real":
                continue
            self._update_job(
                row,
                status="failed",
                verdict=None,
                error={
                    "error_code": "interrupted",
                    "message": "Máy chủ khởi động lại khi job đang chạy; hãy gửi lại file.",
                },
            )
            count += 1
        return count

    def fail(self, job_id: str, error_code: str, message: str) -> None:
        row = self._row(job_id)
        if row is None:
            return
        # Thất bại KHÔNG phải "authentic": verdict để trống.
        self._update_job(
            row,
            status="failed",
            verdict=None,
            error={"error_code": error_code, "message": message},
        )

    # --- đọc ------------------------------------------------------------------
    def get(self, job_id: str) -> ForensicJob | None:
        record = self.db.scalar(
            select(ForensicJobRow).where(ForensicJobRow.job_id == job_id).with_for_update()
        )
        return ForensicJob.model_validate(record.payload["job"]) if record else None

    def report(self, job_id: str) -> tuple[str, str, str] | None:
        """HTML, SHA-256 of exact UTF-8 bytes and detached signature (MOCK for mock jobs)."""
        job = self.report_job(job_id)
        if job is None:
            return None
        if job.status != "done":
            raise ApiError(
                409, "job_not_ready", "Job chưa hoàn tất hoặc đã thất bại; chưa có báo cáo."
            )
        record = self.db.get(ForensicJobRow, job_id)
        if record.payload.get("mode") == "real":
            signer = self.report_signer()
            html = self._report_real(
                job, record.payload, signer.key_id, evidence=self.report_evidence(job, record)
            )
        else:
            signer = None
            html = self._report_mock(job, record)
        digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
        row = self.db.get(ForensicJobRow, job_id)
        row.signature = (
            signer.sign(digest) if signer is not None else f"{MOCK_SIGNATURE_PREFIX}{digest}"
        )
        row.media_deleted_at = None
        row.report_path = str(
            save_generated(
                self.media_dir, "forensic/" + job_id, "report.html", html.encode("utf-8")
            )
        )
        return html, digest, row.signature

    @staticmethod
    def _report_mock(job: ForensicJob, record: ForensicJobRow) -> str:
        disabled_labels = {
            module: evidence["label_vi"]
            for module, result in record.payload.get("module_results", {}).items()
            for evidence in result.get("evidence", [])
            if evidence.get("name") == "orchestration_reason"
            and evidence.get("value") == "disabled_by_profile"
            and isinstance(evidence.get("label_vi"), str)
        }
        rows = "".join(
            f"<tr><td>{s.t_start:g}–{s.t_end:g} s</td>"
            + "".join(
                f"<td>{escape(sig.module)}: "
                + (
                    f"{sig.prob_attack:.2f}"
                    if sig.applicable and sig.prob_attack is not None
                    else escape(disabled_labels.get(sig.module, "—"))
                )
                + "</td>"
                for sig in s.signals
            )
            + "</tr>"
            for s in job.segments
        )
        return (
            '<!doctype html><html lang="vi"><meta charset="utf-8"><title>Báo cáo giám định</title>'
            f"<h1>Báo cáo giám định (bản mock)</h1><p>Mã: {escape(job.job_id)}</p>"
            f"<p>SHA-256 file: {job.file_sha256}</p><p>Kết luận: {job.verdict}</p>"
            f"<table>{rows}</table><h2>Giới hạn</h2>"
            "<p>Dữ liệu mô phỏng, không phải kết quả giám định.</p><ul>"
            + "".join(f"<li>{escape(item)}</li>" for item in LIMITATIONS_VI)
            + "</ul></html>"
        )

    @staticmethod
    def _report_real(
        job: ForensicJob,
        payload: dict[str, Any],
        key_id: str,
        *,
        pdf_bundle: bool = False,
        evidence: ReportEvidence | None = None,
    ) -> str:
        """HTML with a pinned-key identifier; signature covers exact rendered bytes."""
        e = escape

        def cell(sig: SegmentSignal) -> str:
            if sig.status == "ok" and sig.prob_attack is not None:
                return f"{e(sig.module)}: {sig.prob_attack:.2f}"
            label = _STATUS_LABELS_VI.get(sig.status or "", "—")
            reason = f" ({e(sig.reason)})" if sig.reason else ""
            return f"{e(sig.module)}: {label}{reason}"

        rows = "".join(
            f"<tr><td>{s.t_start:g}–{s.t_end:g} s</td>"
            + "".join(f"<td>{cell(sig)}</td>" for sig in s.signals)
            + "</tr>"
            for s in job.segments
        )
        intervals = "".join(
            f"<li>{i.t_start:g}–{i.t_end:g} s ({e(', '.join(i.modules))}"
            + (
                f"; xác suất cao nhất {i.max_prob_attack:.2f}"
                if i.max_prob_attack is not None
                else ""
            )
            + ")</li>"
            for i in job.suspect_intervals
        )
        media = job.media.model_dump(exclude_none=True) if job.media else {}
        media_rows = "".join(f"<li>{e(str(k))}: {e(str(v))}</li>" for k, v in media.items())
        unavailable = "".join(
            f"<li>{e(u.module)}{' (bắt buộc)' if u.required else ''}: {e(u.reason)}</li>"
            for u in job.unavailable_modules
        )
        versions = "".join(
            f"<li>{e(m)}: {e(v)}</li>" for m, v in payload.get("model_versions", {}).items()
        )
        prov = job.provenance
        prov_html = ""
        if prov is not None:
            intervals_wm = "".join(
                f"<li>{w.t_start:g}–{w.t_end:g} s</li>" for w in prov.watermark_intervals
            )
            c2pa = prov.c2pa.model_dump(exclude_none=True) if prov.c2pa else {}
            prov_html = (
                f"<h2>Quét nguồn gốc</h2><p>{e(prov.conclusion)}</p>"
                + (f"<ul>{intervals_wm}</ul>" if intervals_wm else "")
                + (f"<p>C2PA: {e(str(c2pa))}</p>" if c2pa else "")
                + "".join(f"<p><em>{e(n)}</em></p>" for n in prov.notes)
            )
        signature_note = (
            "Chữ ký Ed25519 tách rời trên JSON và hash PDF; không phải chữ ký nhúng PAdES."
            if pdf_bundle
            else "Chữ ký: Ed25519 - ký toàn vẹn báo cáo HTML, không chứng nhận kết luận mô hình."
        )
        pdf_style = (
            """<style>body{font-family:Arial,'DejaVu Sans',sans-serif;font-size:10pt;line-height:1.5;color:#202d3d}h1{font-size:20pt;color:#142f4d;margin:0 0 12px}h2{font-size:12pt;color:#142f4d;margin:18px 0 6px;break-after:avoid}p{margin:6px 0;overflow-wrap:anywhere}ul{padding-left:20px}li{margin:4px 0;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;margin-top:8px;font-size:8.5pt;table-layout:fixed}td,th{border:1px solid #cbd5e1;padding:4px;vertical-align:top;overflow-wrap:anywhere}td:first-child,th:first-child{width:12%}th{background:#eaf0f6;text-align:left}thead{display:table-header-group}tr{break-inside:avoid}strong{color:#92400e}.report-limitations{break-inside:avoid}</style>"""
            if pdf_bundle
            else ""
        )
        report_context = payload.get("pdf_report_context", {}) if pdf_bundle else {}
        context_html = (
            f"<p>Thời điểm tạo job: {e(str(report_context['job_created_at']))}<br>"
            f"Phiên bản VeriClue: {e(str(report_context['tool_version']))}</p>"
            if report_context
            else ""
        )
        anchor = job.review_audit
        link_html = (
            "<h2>Hồ sơ liên kết và mốc nhật ký</h2>"
            f"<p>Ca: {e(anchor.case_id)}; phiên: {e(anchor.session_id)}; bản ghi: {e(anchor.source_role)}.</p>"
            f"<p>SHA-256 bản ghi đã đối chiếu: {anchor.source_sha256}</p>"
            f"<p>Mốc gồm {anchor.event_count} sự kiện; ID cuối: {anchor.tail_event_id}.<br>"
            f"Hash cuối: {anchor.tail_hash}<br>Ghi nhận mốc: {e(anchor.captured_at.isoformat())}</p>"
            "<p>Mốc được ký cùng báo cáo để đối chiếu phần nhật ký đã có. Sự kiện thêm sau mốc "
            "không làm mất hiệu lực phần đã neo; chữ ký không chứng nhận danh tính hoặc kết luận AI.</p>"
            if anchor is not None
            else "<h2>Liên kết hồ sơ</h2><p>Giám định file độc lập.</p>"
        )
        evidence_html = (
            "<style>.report-illustration{margin:12px 0;break-inside:avoid}"
            ".report-illustration img{display:block;max-width:100%;height:auto}"
            ".report-frame img{max-height:55mm;width:auto}"
            ".report-spectrum img{width:100%}"
            ".report-illustration figcaption{font-size:9pt;margin-top:5px;overflow-wrap:anywhere}</style>"
            + evidence.html()
            if evidence is not None
            else ""
        )
        return (
            '<!doctype html><html lang="vi"><meta charset="utf-8"><title>Báo cáo giám định</title>'
            f"{pdf_style}"
            "<h1>Báo cáo giám định</h1>"
            f"<p><strong>{signature_note}</strong></p>"
            + (
                "<p><strong>BẢN THỬ NGHIỆM - chưa có hiệu chỉnh giám định và thang lời ENFSI.</strong></p>"
                if pdf_bundle
                else ""
            )
            + "<p>Chữ ký không chứng nhận kết luận mô hình.</p>"
            + f"<p>Dấu vân tay khóa (SHA-256 SPKI): {e(key_id)}</p>"
            f"{context_html}"
            f"<p>Mã: {e(job.job_id)}</p><p>Tên file: {e(str(payload.get('filename', '')))}</p>"
            f"<p>SHA-256 file (byte gốc): {job.file_sha256}</p>"
            f"{link_html}"
            f"<h2>Thông số file</h2><ul>{media_rows}</ul>"
            f"<h2>Kết luận</h2><p>Kết luận: {job.verdict}</p>"
            f"<p>{e(_VERDICT_LABELS_VI.get(job.verdict or '', ''))}. {e(job.verdict_reason or '')}</p>"
            f"<h2>Khoảng nghi giả (±1 giây)</h2>{'<ul>' + intervals + '</ul>' if intervals else '<p>Không có.</p>'}"
            "<h2>Kết quả theo đoạn</h2><table>"
            + (
                (
                    "<thead><tr><th>Thời gian</th>"
                    + f'<th colspan="{max((len(s.signals) for s in job.segments), default=1)}">Tín hiệu mô hình (chưa phải LR đã hiệu chỉnh)</th></tr></thead>'
                )
                if pdf_bundle
                else ""
            )
            + f"{rows}</table>"
            + evidence_html
            + f"{prov_html}"
            f"<h2>Bước không chạy</h2>{'<ul>' + unavailable + '</ul>' if unavailable else '<p>Không có.</p>'}"
            f"<h2>Phiên bản mô hình</h2>{'<ul>' + versions + '</ul>' if versions else '<p>Không có dữ liệu phiên bản mô hình.</p>'}"
            '<section class="report-limitations"><h2>Giới hạn</h2><ul>'
            + "".join(f"<li>{e(item)}</li>" for item in LIMITATIONS_VI)
            + "</ul></section></html>"
        )

    def report_job(self, job_id: str) -> ForensicJob | None:
        """Refresh linked checkpoints only through prefix validation, before signing either format."""
        job = self.get(job_id)
        if job is None or job.status != "done" or job.review_audit is None:
            return job
        if self._review_links is None:
            raise ApiError(503, "review_link_unavailable", "Chưa thể đối chiếu nhật ký hồ sơ.")
        return self._review_links.refresh(job, self.db.get(ForensicJobRow, job_id))

    def report_evidence(self, job: ForensicJob, row: ForensicJobRow) -> ReportEvidence | None:
        """Server-generated illustrations only; disabled unless explicitly configured."""
        return self._evidence_builder(job, row) if self._evidence_builder else None

    def report_signer(self) -> ReportSigner:
        """Require a configured report key independently of mock/real model startup."""
        if self._report_signer is None:
            raise ApiError(
                503, "report_signing_unavailable", "Chưa thể ký hoặc kiểm tra báo cáo lúc này."
            )
        return self._report_signer()
