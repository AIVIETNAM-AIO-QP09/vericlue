"""ADR-0012 section 6: keep measured lipsync evidence while MVP uses phrase/spoof gates."""

from __future__ import annotations

import time
from contextlib import contextmanager
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import ModuleResultRow, ReviewCaseRow, SessionRow
from vericlue_api.main import create_app
from vericlue_api.services import orchestrator as orchestration
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, ModuleResult, Status
from vericlue_ml.mock.detectors import MockDetector

ADVISORY_LABEL = "Khớp môi chỉ tham khảo ở chế độ MVP"


@pytest.fixture
def advisory_client(monkeypatch):
    @contextmanager
    def start(
        mode="high_score", *, profile="mvp", wrong_phrase=False, spoof_score=0.01, splice_flags=0
    ):
        monkeypatch.setenv("ROUTER_PROFILE", profile)
        monkeypatch.setenv("DETECTOR_TIMEOUT_SECONDS", "0.05" if mode == "timeout" else "1")
        predicted = []
        finished = Event()

        class AdvisoryDetector(MockDetector):
            def preload(self):
                if self.name == Module.LIPSYNC and mode == "preload_failure":
                    raise RuntimeError("Synthetic lipsync preload unavailable")

            def predict(self, inp):
                output = super().predict(inp)
                if self.name == Module.FACE_DEEPFAKE:
                    return output.model_copy(update={"score": 0.45, "prob_attack": 0.45})
                if self.name == Module.VOICE_CHALLENGE:
                    return output.model_copy(
                        update={
                            "gate": Gate.FAIL if wrong_phrase else Gate.PASS,
                            "error_code": ErrorCode.E_CHALLENGE_MISMATCH if wrong_phrase else None,
                        }
                    )
                if self.name == Module.VOICE_SPOOF:
                    return output.model_copy(
                        update={"score": spoof_score, "prob_attack": spoof_score}
                    )
                if self.name != Module.LIPSYNC or "prompt" not in inp.metadata:
                    return output
                predicted.append(inp.session_id)
                if mode == "timeout":
                    try:
                        time.sleep(0.15)
                    finally:
                        finished.set()
                status = {
                    "error": Status.ERROR,
                    "degraded": Status.DEGRADED,
                    "not_applicable": Status.NOT_APPLICABLE,
                }.get(mode, Status.OK)
                return ModuleResult(
                    module=Module.LIPSYNC,
                    model_version="real@missing-calibrator"
                    if mode == "uncalibrated"
                    else self.version,
                    status=status,
                    error_code=ErrorCode.E_LOW_QUALITY if status != Status.OK else None,
                    score=0.99 if status == Status.OK else None,
                    prob_attack=0.99 if status == Status.OK and mode != "uncalibrated" else None,
                    evidence=[
                        Evidence(
                            type="text",
                            name="measurement_marker",
                            value="original lipsync evidence",
                        ),
                        Evidence(type="scalar", name="splice_flags", value=splice_flags),
                    ],
                    latency_ms=1,
                )

        monkeypatch.setattr(
            orchestration, "get_detector", lambda module, *, mock=None: AdvisoryDetector(module)
        )
        get_settings.cache_clear()
        with TestClient(create_app()) as client:
            predicted.clear()
            if mode == "absent":
                engine = client.app.state.vericlue.orchestrator
                original_run = engine.run

                def omit_advisory(*args, **kwargs):
                    output = original_run(*args, **kwargs)
                    if "prompt" in (kwargs.get("extra_metadata") or {}):
                        output.pop(Module.LIPSYNC, None)
                    return output

                monkeypatch.setattr(engine, "run", omit_advisory)
            yield client, predicted
            if mode == "timeout":
                assert finished.wait(timeout=1), "Synthetic inference worker must finish"

    return start


def start_voice(client):
    response = client.post("/v1/sessions")
    assert response.status_code == 200
    created = response.json()
    sid = created["session_id"]
    headers = {"Authorization": "Bearer " + created["token"]}
    face = client.post(f"/v1/sessions/{sid}/finalize", headers=headers)
    assert face.status_code == 200
    assert face.json()["status"] == "voice_challenge"
    return sid, headers


def submit_voice(client, sid, headers):
    return client.post(
        f"/v1/sessions/{sid}/voice",
        headers=headers,
        files={"audio": ("voice.wav", b"synthetic audio", "audio/wav")},
    )


def assert_advisory_payload(payload):
    assert any(
        evidence["name"] == "decision_role"
        and evidence["value"] == "advisory"
        and evidence["label_vi"] == ADVISORY_LABEL
        for evidence in payload["evidence"]
    )


@pytest.mark.parametrize(
    "mode",
    [
        "error",
        "degraded",
        "not_applicable",
        "high_score",
        "uncalibrated",
        "timeout",
        "preload_failure",
        "absent",
    ],
)
def test_mvp_advisory_failure_or_score_does_not_deny_good_required_voice(advisory_client, mode):
    with advisory_client(mode) as (client, predicted):
        sid, headers = start_voice(client)
        response = submit_voice(client, sid, headers)
        assert response.status_code == 200
        assert response.json() == {"status": "pass"}
        with client.app.state.vericlue.database.sessions() as db:
            session = db.get(SessionRow, sid)
            assert session.status == "pass"
            payload = session.payload["results"].get(Module.LIPSYNC)
            rows = db.scalars(
                select(ModuleResultRow)
                .where(ModuleResultRow.session_id == sid, ModuleResultRow.module == Module.LIPSYNC)
                .order_by(ModuleResultRow.id.desc())
            ).all()
            if mode == "absent":
                assert payload is None and rows == []
                assert predicted == [sid]  # It ran; its result was absent from the runner response.
                return
            assert payload is not None
            assert_advisory_payload(payload)
            assert rows and rows[0].payload == ModuleResult.model_validate(payload).to_contract()
            assert rows[0].status == payload["status"]
            if mode in {"timeout", "preload_failure"}:
                assert payload["status"] == "error"
                assert payload.get("prob_attack") is None
                assert payload["error_code"] == ("E_TIMEOUT" if mode == "timeout" else "E_INTERNAL")
                if mode == "timeout":
                    assert predicted == [sid]
                    assert any(e["value"] == "timeout" for e in payload["evidence"])
                else:
                    assert predicted == []
                return
            assert predicted == [sid]
            assert payload["status"] == {
                "error": "error",
                "degraded": "degraded",
                "not_applicable": "not_applicable",
            }.get(mode, "ok")
            assert any(e["name"] == "measurement_marker" for e in payload["evidence"])
            if mode in {"error", "degraded", "not_applicable"}:
                assert payload.get("prob_attack") is None
            else:
                assert payload["score"] == 0.99
                assert payload.get("prob_attack") == (None if mode == "uncalibrated" else 0.99)


@pytest.mark.parametrize("trigger", ["spoof", "splice"])
def test_review_ai_retains_raw_advisory_measurement_and_role(advisory_client, trigger):
    with advisory_client(
        "high_score",
        spoof_score=0.99 if trigger == "spoof" else 0.01,
        splice_flags=2 if trigger == "splice" else 0,
    ) as (client, predicted):
        sid, headers = start_voice(client)
        response = submit_voice(client, sid, headers)
        assert response.status_code == 200
        assert response.json() == {"status": "review"}
        assert predicted == [sid]
        with client.app.state.vericlue.database.sessions() as db:
            case = db.scalar(select(ReviewCaseRow).where(ReviewCaseRow.session_id == sid))
            case_id = case.case_id
            assert case.priority == ("high" if trigger == "splice" else "normal")
            assert_advisory_payload(case.payload["results"][Module.LIPSYNC])
        assert client.get(f"/v1/review/cases/{case_id}/ai").status_code == 409
        initial = client.post(
            f"/v1/review/cases/{case_id}/initial", json={"decision": "request_retry"}
        )
        assert initial.status_code == 200
        ai = client.get(f"/v1/review/cases/{case_id}/ai")
        assert ai.status_code == 200
        lipsync = next(item for item in ai.json()["modules"] if item["module"] == Module.LIPSYNC)
        assert lipsync["status"] == "ok"
        assert lipsync["score"] == lipsync["prob_attack"] == 0.99
        assert any(e["name"] == "measurement_marker" for e in lipsync["evidence"])
        assert_advisory_payload(lipsync)


def test_wrong_phrase_with_splice_rereads_then_reviews_at_normal_priority(advisory_client):
    with advisory_client(wrong_phrase=True, splice_flags=3) as (client, predicted):
        sid, headers = start_voice(client)
        first = submit_voice(client, sid, headers)
        assert first.status_code == 200
        assert first.json()["status"] == "voice_challenge"
        with client.app.state.vericlue.database.sessions() as db:
            assert db.scalar(select(ReviewCaseRow).where(ReviewCaseRow.session_id == sid)) is None
        second = submit_voice(client, sid, headers)
        assert second.status_code == 200
        assert second.json() == {"status": "review"}
        assert predicted == [sid, sid]
        with client.app.state.vericlue.database.sessions() as db:
            case = db.scalar(select(ReviewCaseRow).where(ReviewCaseRow.session_id == sid))
            assert case.priority == "normal"
            assert_advisory_payload(case.payload["results"][Module.LIPSYNC])


def test_full_profile_still_requires_usable_lipsync(advisory_client):
    with advisory_client("error", profile="full") as (client, predicted):
        sid, headers = start_voice(client)
        response = submit_voice(client, sid, headers)
        assert response.status_code == 200
        assert response.json() == {"status": "review"}
        assert predicted == [sid]
        with client.app.state.vericlue.database.sessions() as db:
            payload = db.get(SessionRow, sid).payload["results"][Module.LIPSYNC]
            assert payload["status"] == "error"
            assert not any(e["name"] == "decision_role" for e in payload["evidence"])
