"""Test API giám định /v1/forensic."""

from __future__ import annotations

import hashlib

from contract_utils import validate

DATA = b"abc"


def _create(client, scenario: str | None = None):
    headers = {"X-Mock-Scenario": scenario} if scenario else {}
    return client.post(
        "/v1/forensic/jobs", files={"file": ("a.wav", DATA, "audio/wav")}, headers=headers
    )


def _job(client, scenario: str | None = None) -> dict:
    res = _create(client, scenario)
    assert res.status_code == 200, res.text
    validate(res.json(), "forensic", "JobCreated")
    got = client.get(f"/v1/forensic/jobs/{res.json()['job_id']}")
    assert got.status_code == 200
    validate(got.json(), "forensic", "ForensicJob")
    return got.json()


def test_job_hash_matches_bytes(client):
    assert _job(client)["file_sha256"] == hashlib.sha256(DATA).hexdigest()


def test_verdict_by_scenario(client):
    assert _job(client, "voice_clone")["verdict"] == "suspect"
    assert _job(client)["verdict"] == "authentic"


def test_unknown_scenario_422(client):
    res = _create(client, "khong_co")
    assert res.status_code == 422
    assert res.json()["error_code"] == "unknown_scenario"


def test_report_headers_and_hash(client):
    jid = _job(client)["job_id"]
    res = client.get(f"/v1/forensic/jobs/{jid}/report")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    digest = res.headers["X-VeriClue-Report-SHA256"]
    assert res.headers["X-VeriClue-Signature"]
    assert hashlib.sha256(res.text.encode("utf-8")).hexdigest() == digest


def test_verify_flow(client):
    jid = _job(client)["job_id"]
    res = client.get(f"/v1/forensic/jobs/{jid}/report")
    digest = res.headers["X-VeriClue-Report-SHA256"]
    sig = res.headers["X-VeriClue-Signature"]

    ok = client.post("/v1/forensic/verify", json={"report_sha256": digest, "signature": sig})
    assert ok.status_code == 200
    assert ok.json() == {"valid": True}

    tampered = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    bad = client.post("/v1/forensic/verify", json={"report_sha256": digest, "signature": tampered})
    assert bad.json() == {"valid": False}

    malformed = client.post("/v1/forensic/verify", json={"report_sha256": "xyz", "signature": sig})
    assert malformed.status_code == 422


def test_unknown_job_404(client):
    assert client.get("/v1/forensic/jobs/job_none").status_code == 404
    assert client.get("/v1/forensic/jobs/job_none/report").status_code == 404
