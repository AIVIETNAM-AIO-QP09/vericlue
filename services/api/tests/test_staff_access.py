"""Staff guards use actual configured credentials, including fully mocked demos."""

import json
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import DecisionRow, ReviewEventRow
from vericlue_api.main import create_app


@pytest.fixture
def anonymous_factory():
    clients = []

    def make(**options):
        # No lifespan: rejected HTTP requests must not initialize models or DB.
        get_settings.cache_clear()
        client = TestClient(create_app(), **options)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
        client.app.state.vericlue.orchestrator.close()
        client.app.state.vericlue.database.dispose()


@pytest.fixture
def anonymous(anonymous_factory):
    return anonymous_factory()


def auth(client):
    tokens = json.loads(client.app.state.vericlue.settings.staff_access_tokens.get_secret_value())
    return {"Authorization": "Bearer " + next(iter(tokens))}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/review/cases"),
        ("GET", "/v1/review/reason-codes"),
        ("GET", "/v1/review/cases/unknown"),
        ("GET", "/v1/review/cases/unknown/identity"),
        ("POST", "/v1/review/cases/unknown/identity/reveal"),
        ("POST", "/v1/review/cases/unknown/initial"),
        ("GET", "/v1/review/cases/unknown/ai"),
        ("POST", "/v1/review/cases/unknown/decision"),
        ("GET", "/v1/review/cases/unknown/audit/verify"),
        ("POST", "/v1/forensic/jobs"),
        ("GET", "/v1/forensic/jobs/unknown"),
        ("GET", "/v1/forensic/jobs/unknown/report"),
        ("POST", "/v1/forensic/verify"),
    ],
)
def test_every_staff_endpoint_requires_auth_before_parsing_or_storage(anonymous, method, path):
    response = anonymous.request(method, path)
    assert response.status_code == 401, response.text
    assert response.json() == {
        "error_code": "unauthorized",
        "message": "Thiếu hoặc sai quyền truy cập.",
    }
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["Cache-Control"] == "no-store"
    assert not anonymous.app.state.vericlue._initialized


@pytest.mark.parametrize("mode", ["true", "false", "mixed"])
@pytest.mark.parametrize("privacy", ["true", "false"])
def test_privacy_or_mock_flags_cannot_disable_staff_auth(
    monkeypatch,
    mode,
    privacy,
    anonymous_factory,
):
    monkeypatch.setenv("USE_MOCK_MODELS", mode)
    monkeypatch.setenv("SESSION_PRIVACY", privacy)
    client = anonymous_factory()
    for path in ("/v1/review/reason-codes", "/v1/forensic/jobs/missing"):
        assert client.get(path).status_code == 401
    assert not client.app.state.vericlue._initialized
    # This endpoint needs no DB/models, so authorization can be checked in real mode too.
    assert client.get("/v1/review/reason-codes", headers=auth(client)).status_code == 200
    assert not client.app.state.vericlue._initialized


@pytest.mark.parametrize(
    "config",
    [
        None,
        "",
        "{}",
        "[]",
        "not-json",
        "[" * 1100 + "]" * 1100,
        json.dumps({"short": "actor"}),
        json.dumps({"x" * 32: ""}),
        json.dumps({"x" * 32: " "}),
        json.dumps({"x" * 32: "staff-unverified"}),
        json.dumps({"x" * 32: "actor\nspoof"}),
        json.dumps({"x" * 32: 1}),
        json.dumps({"x" * 32: "a" * 101}),
        json.dumps({"é" * 32: "actor"}),
        json.dumps({"x" * 513: "actor"}),
        '{"' + "x" * 32 + '":"actor1","' + "x" * 32 + '":"actor2"}',
    ],
)
def test_missing_or_invalid_configuration_fails_closed(monkeypatch, anonymous_factory, config):
    if config is None:
        monkeypatch.delenv("STAFF_ACCESS_TOKENS")
    else:
        monkeypatch.setenv("STAFF_ACCESS_TOKENS", config)
    client = anonymous_factory()
    for path in ("/v1/review/cases", "/v1/forensic/jobs/missing/report"):
        response = client.get(path, headers={"Authorization": "Bearer " + "x" * 32})
        assert response.status_code == 503
        assert response.json()["error_code"] == "staff_unavailable"
        assert response.headers["Cache-Control"] == "no-store"
        assert "actor1" not in response.text and "x" * 32 not in response.text
    assert not client.app.state.vericlue._initialized
    assert client.get("/healthz").status_code == 200


@pytest.mark.parametrize(
    "value",
    [
        "",
        "Basic dGVzdDp0ZXN0",
        "Bearer wrong",
        "Bearer " + "x" * 513,
        "Bearer caf\xe9",
        "Bearer  " + "x" * 32,
    ],
)
def test_invalid_authorization_is_generic_401(anonymous, value):
    response = anonymous.get("/v1/review/cases", headers={"Authorization": value.encode("latin1")})
    assert response.status_code == 401
    assert "x" * 32 not in response.text
    assert not anonymous.app.state.vericlue._initialized


def test_multiple_authorization_values_are_rejected_even_with_a_valid_token(anonymous):
    valid = auth(anonymous)["Authorization"]
    for pairs in (
        [("Authorization", valid), ("Authorization", valid)],
        [("Authorization", valid), ("Authorization", "Bearer wrong")],
    ):
        assert anonymous.get("/v1/review/cases", headers=pairs).status_code == 401
    assert not anonymous.app.state.vericlue._initialized


def test_tokens_in_query_or_cookie_and_actor_headers_are_not_credentials(anonymous):
    token = auth(anonymous)["Authorization"].removeprefix("Bearer ")
    assert anonymous.get("/v1/review/cases", params={"access_token": token}).status_code == 401
    assert (
        anonymous.get("/v1/review/cases", headers={"Cookie": "access_token=" + token}).status_code
        == 401
    )
    assert anonymous.get("/v1/review/cases", headers={"X-Staff-Actor": "admin"}).status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/v1/review",
        "/v1/review/",
        "/v1/review%2Fcases",
        "/v1/forensic",
        "/v1/forensic/",
        "/v1/forensic%2Fjobs/missing/report",
    ],
)
def test_decoded_and_base_paths_cannot_bypass_guard(anonymous, path):
    assert anonymous.get(path).status_code == 401


def test_root_path_and_non_staff_lookalike(anonymous_factory):
    client = anonymous_factory(root_path="/gateway")
    assert client.get("/gateway/v1/review/cases").status_code == 401
    assert client.get("/gateway/v1/forensic/jobs/missing/report").status_code == 401
    assert client.get("/gateway/v1/reviewer/cases").status_code == 404
    assert client.get("/gateway/v1/review/reason-codes", headers=auth(client)).status_code == 200


def test_cors_preflight_and_auth_errors_remain_readable(monkeypatch, anonymous_factory):
    monkeypatch.delenv("STAFF_ACCESS_TOKENS")
    client = anonymous_factory()
    origin = {"Origin": "http://localhost:3000"}
    preflight = client.options(
        "/v1/forensic/jobs",
        headers={
            **origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert preflight.status_code == 200
    assert client.post("/v1/forensic/jobs", headers=origin).status_code == 503
    monkeypatch.setenv("STAFF_ACCESS_TOKENS", json.dumps({secrets.token_urlsafe(32): "actor"}))
    client = anonymous_factory()
    rejected = client.post("/v1/forensic/jobs", headers=origin)
    assert rejected.status_code == 401
    assert rejected.headers["access-control-allow-origin"] == origin["Origin"]
    assert "WWW-Authenticate" in rejected.headers["access-control-expose-headers"]


def test_rejected_upload_does_not_read_body_or_initialize_app(anonymous):
    def forbidden_stream():
        pytest.fail("Unauthorized upload must be rejected before consuming the body")
        yield b""  # pragma: no cover

    response = anonymous.post(
        "/v1/forensic/jobs",
        content=forbidden_stream(),
        headers={"Content-Type": "multipart/form-data; boundary=unused"},
    )
    assert response.status_code == 401
    assert not anonymous.app.state.vericlue._initialized


def test_citizen_and_staff_credentials_are_not_interchangeable(anonymous):
    session = anonymous.post("/v1/sessions").json()
    citizen = {"Authorization": "Bearer " + session["token"]}
    assert anonymous.get("/v1/review/cases", headers=citizen).status_code == 401
    assert anonymous.get("/v1/forensic/jobs/missing", headers=citizen).status_code == 401
    assert (
        anonymous.post(
            f"/v1/sessions/{session['session_id']}/finalize", headers=auth(anonymous)
        ).status_code
        == 401
    )


def test_review_audit_uses_configured_actor_independent_of_privacy(anonymous):
    headers = {**auth(anonymous), "X-Staff-Actor": "spoofed-admin"}
    listed = anonymous.get("/v1/review/cases", headers=headers)
    assert listed.status_code == 200 and listed.headers["Cache-Control"] == "no-store"
    case = listed.json()["items"][0]
    base = f"/v1/review/cases/{case['case_id']}"
    assert (
        anonymous.post(base + "/initial", headers=headers, json={"decision": "accept"}).status_code
        == 200
    )
    assert (
        anonymous.post(
            base + "/decision",
            headers=headers,
            json={
                "decision": "accept",
                "reason_code": "AI_AGREES",
            },
        ).status_code
        == 200
    )
    with anonymous.app.state.vericlue.database.sessions() as db:
        events = list(
            db.scalars(select(ReviewEventRow).where(ReviewEventRow.case_id == case["case_id"]))
        )
        assert len(events) == 2 and all(event.actor == "staff-test" for event in events)
        decision = db.scalar(
            select(DecisionRow).where(DecisionRow.session_id == case["session_id"])
        )
        assert decision.config_version == "staff-authenticated@PLAT-06"
    assert anonymous.get(base + "/audit/verify", headers=headers).json()["ok"]


def test_forensic_flow_requires_staff_for_upload_result_report_and_verify(anonymous):
    headers = auth(anonymous)
    created = anonymous.post(
        "/v1/forensic/jobs",
        headers=headers,
        files={"file": ("synthetic.wav", b"synthetic audio", "audio/wav")},
    )
    assert created.status_code == 200, created.text
    base = "/v1/forensic/jobs/" + created.json()["job_id"]
    for path in (base, base + "/report"):
        assert anonymous.get(path).status_code == 401
        response = anonymous.get(path, headers=headers)
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
    report = anonymous.get(base + "/report", headers=headers)
    payload = {
        "report_sha256": report.headers["X-VeriClue-Report-SHA256"],
        "signature": report.headers["X-VeriClue-Signature"],
    }
    assert anonymous.post("/v1/forensic/verify", json=payload).status_code == 401
    assert anonymous.post("/v1/forensic/verify", json=payload, headers=headers).json() == {
        "valid": True
    }
    missing = anonymous.get("/v1/forensic/jobs/unknown", headers=headers)
    assert missing.status_code == 404 and missing.headers["Cache-Control"] == "no-store"


def test_openapi_marks_all_review_and_forensic_operations_as_staff_protected(anonymous):
    spec = anonymous.get("/openapi.json").json()
    for path, methods in spec["paths"].items():
        if path.startswith(("/v1/review/", "/v1/forensic/")):
            for method, operation in methods.items():
                if method in {"get", "post"}:
                    assert {"StaffBearer": []} in operation["security"]
                    assert {"401", "503"} <= operation["responses"].keys()
