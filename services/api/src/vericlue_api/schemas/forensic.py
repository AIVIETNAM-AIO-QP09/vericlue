"""Model Pydantic khớp `forensic.schema.json` (draft v1; các trường sau v1 đều tùy chọn)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "done", "failed"]
Verdict = Literal["authentic", "suspect", "inconclusive"]
# unavailable = module chưa có mô hình thật hoặc bị tắt: không chạy, không giả lập.
SignalStatus = Literal["ok", "not_applicable", "degraded", "error", "unavailable"]


class SegmentSignal(BaseModel):
    module: str
    applicable: bool
    prob_attack: float | None = Field(default=None, ge=0, le=1)
    status: SignalStatus | None = None
    reason: str | None = None


class ForensicSegment(BaseModel):
    t_start: float = Field(ge=0)
    t_end: float = Field(ge=0)
    signals: list[SegmentSignal]


class JobCreated(BaseModel):
    job_id: str
    status: JobStatus


class ForensicProgress(BaseModel):
    stage: str | None = None
    segments_done: int = Field(ge=0)
    segments_total: int = Field(ge=0)


class ForensicError(BaseModel):
    error_code: str
    message: str


class ForensicMedia(BaseModel):
    kind: Literal["video", "audio"] | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    duration_s: float | None = Field(default=None, ge=0)
    container: str | None = None
    video_codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    bitrate_kbps: float | None = None
    has_audio: bool | None = None
    audio_codec: str | None = None
    audio_sample_rate: int | None = None


class SuspectInterval(BaseModel):
    t_start: float = Field(ge=0)
    t_end: float = Field(ge=0)
    modules: list[str] = Field(default_factory=list)
    max_prob_attack: float | None = Field(default=None, ge=0, le=1)


class UnavailableModule(BaseModel):
    module: str
    reason: str
    required: bool | None = None


class WatermarkInterval(BaseModel):
    t_start: float = Field(ge=0)
    t_end: float = Field(ge=0)
    prob: float | None = Field(default=None, ge=0, le=1)


class C2paInfo(BaseModel):
    status: SignalStatus | None = None
    present: bool | None = None
    valid: bool | None = None
    signer: str | None = None
    ai_generated: bool | None = None
    note: str | None = None


class ForensicProvenance(BaseModel):
    status: SignalStatus
    conclusion: str
    watermark_detected: bool | None = None
    tool: str | None = None
    watermark_intervals: list[WatermarkInterval] = Field(default_factory=list)
    c2pa: C2paInfo | None = None
    notes: list[str] = Field(default_factory=list)


class ForensicJob(BaseModel):
    job_id: str
    status: JobStatus
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Verdict | None = None
    segments: list[ForensicSegment]
    progress: ForensicProgress | None = None
    error: ForensicError | None = None
    media: ForensicMedia | None = None
    suspect_intervals: list[SuspectInterval] = Field(default_factory=list)
    unavailable_modules: list[UnavailableModule] = Field(default_factory=list)
    provenance: ForensicProvenance | None = None
    verdict_reason: str | None = None


class VerifyRequest(BaseModel):
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str


class VerifyResponse(BaseModel):
    valid: bool
