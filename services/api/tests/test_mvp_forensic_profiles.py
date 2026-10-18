"""Disabled MVP steps remain explicit for forensic/staff users without running models."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import ForensicJobRow, ForensicSegmentRow, ReviewCaseRow
from vericlue_api.main import create_app
from vericlue_ml.common.result import Module

DISABLED_LABEL = "Bước này đang tắt ở chế độ MVP"
FORENSIC_MODULES = {"face_deepfake", "voice_spoof", "lipsync", "provenance"}
DISABLED_FORENSIC = {"lipsync", "provenance"}


@pytest.mark.parametrize("profile,verdict", [("full", "authentic"), ("mvp", "inconclusive")])
def test_forensic_genuine_does_not_authenticate_when_mvp_steps_are_disabled(
    monkeypatch: pytest.MonkeyPatch, profile: str, verdict: str
) -> None:
    monkeypatch.setenv("ROUTER_PROFILE", profile)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        created = client.post(
            "/v1/forensic/jobs",
            headers={"X-Mock-Scenario": "genuine"},
            files={"file": ("fixture.wav", b"synthetic audio", "audio/wav")},
        )
        assert created.status_code == 200
        job_id = created.json()["job_id"]
        response = client.get(f"/v1/forensic/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        assert job["verdict"] == verdict
        for segment in job["segments"]:
            signals = {signal["module"]: signal for signal in segment["signals"]}
            assert set(signals) == FORENSIC_MODULES
            for module in DISABLED_FORENSIC:
                assert signals[module]["applicable"] is (profile == "full")
                if profile == "mvp":
                    assert signals[module]["prob_attack"] is None
        report = client.get(f"/v1/forensic/jobs/{job_id}/report")
        assert report.status_code == 200
        assert f"Kết luận: {verdict}" in report.text
        if profile == "mvp":
            assert DISABLED_LABEL in report.text
            assert all(module in report.text for module in DISABLED_FORENSIC)
        else:
            assert DISABLED_LABEL not in report.text
        with client.app.state.vericlue.database.sessions() as db:
            row = db.get(ForensicJobRow, job_id)
            assert row.verdict == verdict
            assert row.payload["job"] == job
            segments = db.scalars(
                select(ForensicSegmentRow).where(ForensicSegmentRow.job_id == job_id)
            ).all()
            assert len(segments) == len(job["segments"])
            for segment in segments:
                signals = {signal["module"]: signal for signal in segment.signals}
                assert set(signals) == FORENSIC_MODULES
                if profile == "mvp":
                    assert all(not signals[module]["applicable"] for module in DISABLED_FORENSIC)
            if profile == "mvp":
                persisted = json.dumps(row.payload, ensure_ascii=False)
                assert "disabled_by_profile" in persisted
                assert DISABLED_LABEL in persisted
                for module in DISABLED_FORENSIC:
                    result = row.payload["module_results"][module]
                    assert result["status"] == "error"
                    assert result["error_code"] == "E_INTERNAL"
                    assert any(
                        evidence["value"] == "disabled_by_profile"
                        and evidence["label_vi"] == DISABLED_LABEL
                        for evidence in result["evidence"]
                    )


def test_mvp_review_seed_retains_disabled_step_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTER_PROFILE", "mvp")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        with client.app.state.vericlue.database.sessions() as db:
            cases = db.scalars(select(ReviewCaseRow)).all()
            assert cases
            identifiers = [row.case_id for row in cases]
            for row in cases:
                disabled = row.payload["results"][Module.CHROMAPULSE]
                assert disabled["status"] == "error"
                assert disabled["error_code"] == "E_INTERNAL"
                assert any(
                    evidence["name"] == "orchestration_reason"
                    and evidence["value"] == "disabled_by_profile"
                    and evidence["label_vi"] == DISABLED_LABEL
                    for evidence in disabled["evidence"]
                )
        with client.app.state.vericlue.transaction() as state:
            for identifier in identifiers:
                opinion = state.reviews.get(identifier).ai_opinion(
                    state.settings.router_config.face.b
                )
                assert opinion.suggestion == "review"
                disabled = next(
                    result for result in opinion.modules if result["module"] == Module.CHROMAPULSE
                )
                assert disabled["status"] == "error"
                assert any(
                    evidence["label_vi"] == DISABLED_LABEL for evidence in disabled["evidence"]
                )
