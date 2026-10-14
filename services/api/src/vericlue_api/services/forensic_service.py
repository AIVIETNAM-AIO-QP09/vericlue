"""Giám định (mock): TẠM — FOR-01/FOR-04 thay bằng phân đoạn thật và chữ ký Ed25519 (PLAT-06)."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from html import escape

from vericlue_api.schemas.forensic import ForensicJob, ForensicSegment, SegmentSignal, Verdict
from vericlue_api.services.detection import run_detectors
from vericlue_ml.common.result import Module, ModuleResult, Status

FORENSIC_MODULES = (Module.FACE_DEEPFAKE, Module.VOICE_SPOOF, Module.LIPSYNC, Module.PROVENANCE)
SEGMENT_SECONDS = 5.0
SEGMENTS = 2
MOCK_SIGNATURE_PREFIX = "MOCK-"  # TẠM — chữ ký thật là Ed25519


def _signal(r: ModuleResult) -> SegmentSignal:
    return SegmentSignal(
        module=str(r.module), applicable=r.status == Status.OK, prob_attack=r.prob_attack
    )


@dataclass
class JobRecord:
    job: ForensicJob
    filename: str


class ForensicStore:
    def __init__(self, b: float, a: float) -> None:
        self._b, self._a = b, a
        self._jobs: dict[str, JobRecord] = {}

    def create(self, data: bytes, filename: str | None, scenario: str) -> ForensicJob:
        results = run_detectors(FORENSIC_MODULES, session_id=None, scenario=scenario)
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
        self._jobs[job.job_id] = JobRecord(job=job, filename=filename or "")
        return job

    def get(self, job_id: str) -> ForensicJob | None:
        record = self._jobs.get(job_id)
        return record.job if record else None

    def report(self, job_id: str) -> tuple[str, str, str] | None:
        """(html, sha256 của html, chữ ký mock)."""
        job = self.get(job_id)
        if job is None:
            return None
        rows = "".join(
            f"<tr><td>{s.t_start:g}–{s.t_end:g} s</td>"
            + "".join(
                f"<td>{escape(sig.module)}: "
                + (
                    f"{sig.prob_attack:.2f}"
                    if sig.applicable and sig.prob_attack is not None
                    else "—"
                )
                + "</td>"
                for sig in s.signals
            )
            + "</tr>"
            for s in job.segments
        )
        html = (
            '<!doctype html><html lang="vi"><meta charset="utf-8"><title>Báo cáo giám định</title>'
            f"<h1>Báo cáo giám định (bản mock)</h1><p>Mã: {escape(job.job_id)}</p>"
            f"<p>SHA-256 file: {job.file_sha256}</p><p>Kết luận: {job.verdict}</p>"
            f"<table>{rows}</table></html>"
        )
        digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
        return html, digest, f"{MOCK_SIGNATURE_PREFIX}{digest}"

    @staticmethod
    def verify(report_sha256: str, signature: str) -> bool:
        return signature == f"{MOCK_SIGNATURE_PREFIX}{report_sha256}"
