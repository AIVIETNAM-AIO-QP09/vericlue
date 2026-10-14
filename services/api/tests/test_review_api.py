"""Test API bàn duyệt /v1/review."""

from __future__ import annotations

from typing import Any

from conftest import start_session
from contract_utils import validate

FINAL = {"decision": "accept", "reason_code": "ok"}
FORBIDDEN_KEYS = {"score", "prob_attack", "gate", "modules", "suggestion"}


def _keys(node: Any) -> set[str]:
    """Mọi khóa xuất hiện ở bất kỳ độ sâu nào."""
    found: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            found.add(k)
            found |= _keys(v)
    elif isinstance(node, list):
        for v in node:
            found |= _keys(v)
    return found


def _cases(client, **params) -> list[dict]:
    res = client.get("/v1/review/cases", params=params)
    assert res.status_code == 200, res.text
    validate(res.json(), "review", "ReviewCaseList")
    return res.json()["items"]


def _first_id(client) -> str:
    return _cases(client)[0]["case_id"]


def test_list_cases_and_priority_order(client):
    items = _cases(client)
    assert len(items) >= 2
    assert items[0]["priority"] == "high"


def test_list_filter_priority(client):
    items = _cases(client, priority="high")
    assert items
    assert all(c["priority"] == "high" for c in items)


def test_list_filter_status_closed_empty(client):
    assert _cases(client, status="closed") == []


def test_get_case_has_no_ai_fields(client):
    res = client.get(f"/v1/review/cases/{_first_id(client)}")
    assert res.status_code == 200
    validate(res.json(), "review", "ReviewCase")
    assert not (_keys(res.json()) & FORBIDDEN_KEYS)


def test_get_case_not_found(client):
    res = client.get("/v1/review/cases/khong_ton_tai")
    assert res.status_code == 404
    assert set(res.json()) == {"error_code", "message"}


def test_ai_requires_initial_then_flow(client):
    cid = _first_id(client)
    assert client.get(f"/v1/review/cases/{cid}/ai").status_code == 409

    res = client.post(f"/v1/review/cases/{cid}/initial", json={"decision": "accept"})
    assert res.status_code == 200
    validate(res.json(), "review", "DecisionResponse")
    assert res.json()["status"] == "initial_decided"

    ai = client.get(f"/v1/review/cases/{cid}/ai")
    assert ai.status_code == 200
    validate(ai.json(), "review", "ReviewAiOpinion")

    again = client.post(f"/v1/review/cases/{cid}/initial", json={"decision": "reject"})
    assert again.status_code == 409


def test_final_decision_requires_initial(client):
    cid = _first_id(client)
    early = client.post(f"/v1/review/cases/{cid}/decision", json=FINAL)
    assert early.status_code == 409

    client.post(f"/v1/review/cases/{cid}/initial", json={"decision": "accept"})
    res = client.post(f"/v1/review/cases/{cid}/decision", json={**FINAL, "decision": "reject"})
    assert res.status_code == 200
    validate(res.json(), "review", "DecisionResponse")
    assert res.json()["status"] == "closed"

    case = client.get(f"/v1/review/cases/{cid}").json()
    assert case["final_decision"] == "reject"
    assert case["status"] == "closed"


def test_invalid_decision_body_422(client):
    cid = _first_id(client)
    res = client.post(f"/v1/review/cases/{cid}/initial", json={"decision": "la"})
    assert res.status_code == 422
    assert res.json()["error_code"] == "validation_error"


def test_finalize_review_creates_case(client):
    before = {c["case_id"] for c in _cases(client)}
    body, headers = start_session(client, "print")
    sid = body["session_id"]
    res = client.post(f"/v1/sessions/{sid}/finalize", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "review"

    new = [c for c in _cases(client) if c["case_id"] not in before]
    assert [c["session_id"] for c in new] == [sid]
