"""Model Pydantic khớp `forensic.schema.json` (draft v1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "done", "failed"]
Verdict = Literal["authentic", "suspect", "inconclusive"]


class SegmentSignal(BaseModel):
    module: str
    applicable: bool
    prob_attack: float | None = Field(default=None, ge=0, le=1)


class ForensicSegment(BaseModel):
    t_start: float = Field(ge=0)
    t_end: float = Field(ge=0)
    signals: list[SegmentSignal]


class JobCreated(BaseModel):
    job_id: str
    status: JobStatus


class ForensicJob(BaseModel):
    job_id: str
    status: JobStatus
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Verdict | None = None
    segments: list[ForensicSegment]


class VerifyRequest(BaseModel):
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str


class VerifyResponse(BaseModel):
    valid: bool
