"""Test OpenAPI: đủ endpoint, bảo mật Bearer, lỗi 401/409 được khai báo."""

from __future__ import annotations

import pytest

S = "/v1/sessions/{session_id}"
EXPECTED = {
    ("get", "/healthz"),
    ("post", "/v1/sessions"),
    ("post", f"{S}/media"),
    ("post", f"{S}/signals"),
    ("post", f"{S}/finalize"),
    ("post", f"{S}/voice"),
    ("post", f"{S}/otp"),
    ("post", f"{S}/otp/verify"),
    ("post", f"{S}/id-card"),
    ("post", f"{S}/id-card/confirm"),
    ("post", f"{S}/challenge"),
    ("get", "/v1/review/cases"),
    ("get", "/v1/review/cases/{case_id}"),
    ("post", "/v1/review/cases/{case_id}/initial"),
    ("get", "/v1/review/cases/{case_id}/ai"),
    ("post", "/v1/review/cases/{case_id}/decision"),
    ("post", "/v1/forensic/jobs"),
    ("get", "/v1/forensic/jobs/{job_id}"),
    ("get", "/v1/forensic/jobs/{job_id}/report"),
    ("post", "/v1/forensic/verify"),
}


@pytest.fixture
def spec(client) -> dict:
    res = client.get("/openapi.json")
    assert res.status_code == 200
    return res.json()


def test_all_endpoints_present(spec):
    have = {(m, p) for p, ops in spec["paths"].items() for m in ops}
    assert have >= EXPECTED, EXPECTED - have


def test_bearer_security_scheme(spec):
    schemes = spec["components"]["securitySchemes"].values()
    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemes)


@pytest.mark.parametrize("step", ["media", "signals", "finalize", "voice"])
def test_session_steps_declare_401_409(spec, step):
    responses = spec["paths"][f"{S}/{step}"]["post"]["responses"]
    assert "401" in responses
    assert "409" in responses


def test_docs_page(client):
    assert client.get("/docs").status_code == 200
