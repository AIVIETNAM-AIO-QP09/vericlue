"""Mô hình Pydantic của giám định với trường tối thiểu/null phải hợp lệ theo forensic.schema.json."""

from __future__ import annotations

import pytest
from contract_utils import validate

from vericlue_api.schemas.forensic import (
    C2paInfo,
    ForensicJob,
    ForensicMedia,
    ForensicProgress,
    ForensicProvenance,
    ForensicSegment,
    SegmentSignal,
    SuspectInterval,
    UnavailableModule,
)

SHA = "0" * 64


def _dump(job: ForensicJob) -> dict:
    return job.model_dump(mode="json")  # giữ nguyên các trường null, như response API


def test_job_toi_thieu_hop_le():
    job = ForensicJob(job_id="job_x", status="queued", file_sha256=SHA, segments=[])
    validate(_dump(job), "forensic", "ForensicJob")


def test_job_voi_moi_object_tuy_chon_rong_van_hop_le():
    job = ForensicJob(
        job_id="job_x",
        status="done",
        file_sha256=SHA,
        verdict="inconclusive",
        segments=[
            ForensicSegment(
                t_start=0,
                t_end=1,
                signals=[SegmentSignal(module="face_deepfake", applicable=False)],
            )
        ],
        progress=ForensicProgress(segments_done=0, segments_total=0),
        media=ForensicMedia(),
        suspect_intervals=[SuspectInterval(t_start=0, t_end=1)],
        unavailable_modules=[UnavailableModule(module="m", reason="r")],
        provenance=ForensicProvenance(status="ok", conclusion="x", c2pa=C2paInfo()),
    )
    data = _dump(job)
    # các trường null đi qua JSON thật sự có mặt
    assert data["media"]["kind"] is None and data["media"]["size_bytes"] is None
    assert data["progress"]["stage"] is None
    assert data["unavailable_modules"][0]["required"] is None
    assert data["provenance"]["watermark_detected"] is None
    assert data["provenance"]["c2pa"]["status"] is None
    validate(data, "forensic", "ForensicJob")


@pytest.mark.parametrize("c2pa", [None, C2paInfo(status="unavailable", note="Chưa cài c2pa")])
def test_provenance_c2pa_null_hoac_unavailable_hop_le(c2pa):
    job = ForensicJob(
        job_id="job_x",
        status="done",
        file_sha256=SHA,
        segments=[],
        provenance=ForensicProvenance(status="unavailable", conclusion="x", c2pa=c2pa),
    )
    validate(_dump(job), "forensic", "ForensicJob")
