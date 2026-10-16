"""Test API bàn duyệt: mã lý do, ý kiến AI, nhật ký băm, đồng thời."""

from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vericlue_api.core.config import get_settings
from vericlue_api.main import create_app

FORBIDDEN_KEYS = {"score", "prob_attack", "modules"}


def _keys(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            found.add(k)
            found |= _keys(v)
    elif isinstance(node, list):
        for v in node:
            found |= _keys(v)
    return found


def _first_id(client) -> str:
    return client.get("/v1/review/cases").json()["items"][0]["case_id"]


def _initial(client, cid, decision="accept", note=None):
    return client.post(f"/v1/review/cases/{cid}/initial", json={"decision": decision, "note": note})


def _final(client, cid, code="AI_AGREES", note=None, decision="accept"):
    body = {"decision": decision, "reason_code": code}
    if note is not None:
        body["note"] = note
    return client.post(f"/v1/review/cases/{cid}/decision", json=body)


def _verify(client, cid) -> dict:
    res = client.get(f"/v1/review/cases/{cid}/audit/verify")
    assert res.status_code == 200, res.text
    return res.json()


def test_ai_before_initial_is_409(client):
    res = client.get(f"/v1/review/cases/{_first_id(client)}/ai")
    assert res.status_code == 409
    assert res.json()["error_code"] == "initial_decision_required"


def test_invalid_reason_code_422_and_case_stays_open(client):
    cid = _first_id(client)
    assert _initial(client, cid).status_code == 200
    res = _final(client, cid, code="KHONG_CO")
    assert res.status_code == 422
    assert res.json()["error_code"] == "invalid_reason_code"
    case = client.get(f"/v1/review/cases/{cid}").json()
    assert case["status"] == "initial_decided"
    assert case["final_decision"] is None
    assert [h["action"] for h in case["history"]] == ["initial"]
    assert _verify(client, cid)["checked"] == 1


def test_other_requires_note(client):
    cid = _first_id(client)
    _initial(client, cid)
    for note in (None, "   "):
        res = _final(client, cid, code="OTHER", note=note)
        assert res.status_code == 422
        assert res.json()["error_code"] == "invalid_reason_code"
    assert _final(client, cid, code="OTHER", note="Lý do riêng").status_code == 200


def test_reason_codes_list(client):
    items = client.get("/v1/review/reason-codes").json()["items"]
    assert len(items) == 9
    by_code = {i["code"]: i for i in items}
    assert "SYSTEM_DEGRADED" in by_code
    assert by_code["OTHER"]["note_required"] is True
    assert [c for c, i in by_code.items() if i["note_required"]] == ["OTHER"]


def test_case_has_no_scores_and_history_in_order(client):
    cid = _first_id(client)
    _initial(client, cid, "reject", note="nghi ngờ")
    assert _final(client, cid, "SPOOF_CONFIRMED", decision="reject").status_code == 200
    case = client.get(f"/v1/review/cases/{cid}").json()
    assert not (_keys(case) & FORBIDDEN_KEYS)
    assert [h["action"] for h in case["history"]] == ["initial", "final"]
    assert case["history"][0]["note"] == "nghi ngờ"
    assert case["history"][1]["reason_code"] == "SPOOF_CONFIRMED"
    assert case["status"] == "closed"


def test_verify_ok_after_two_events(client):
    cid = _first_id(client)
    _initial(client, cid)
    _final(client, cid)
    body = _verify(client, cid)
    assert body["ok"] is True and body["checked"] == 2
    assert body["bad_index"] is None


def _tamper(cid: str, which: str, key: str, value: str) -> None:
    """Chỉ trên DB test: rút trigger append-only rồi sửa payload của một sự kiện."""
    path = os.environ["DATABASE_URL"].removeprefix("sqlite:///")
    con = sqlite3.connect(path)
    try:
        con.execute("DROP TRIGGER review_events_no_update")
        con.execute(
            f"UPDATE review_events SET payload = json_set(payload, '$.{key}', ?) "
            f"WHERE id = (SELECT {which}(id) FROM review_events WHERE case_id = ?)",
            (value, cid),
        )
        con.commit()
    finally:
        con.close()


def test_tamper_first_event_detected(client):
    cid = _first_id(client)
    _initial(client, cid)
    _final(client, cid)
    _tamper(cid, "MIN", "decision", "reject")
    body = _verify(client, cid)
    assert (body["ok"], body["bad_index"], body["reason"]) == (False, 0, "hash_mismatch")


def test_tamper_second_event_detected(client):
    cid = _first_id(client)
    _initial(client, cid)
    _final(client, cid)
    _tamper(cid, "MAX", "note", "sửa lén")
    body = _verify(client, cid)
    assert (body["ok"], body["bad_index"], body["reason"]) == (False, 1, "hash_mismatch")


def test_seed_demo_mock_has_two_cases(client):
    assert len(client.get("/v1/review/cases").json()["items"]) == 2


def test_seed_demo_absent_without_mock(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/v1/review/cases").json()["items"] == []


def test_concurrent_initial_exactly_one_wins(client):
    cid = _first_id(client)
    barrier = Barrier(2)

    def go(decision):
        barrier.wait(timeout=5)
        return _initial(client, cid, decision)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(go, d) for d in ("accept", "reject")]
        results = [f.result(timeout=15) for f in futures]
    assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
    loser = next(r for r in results if r.status_code == 409)
    assert loser.json()["error_code"] in {"initial_already_recorded", "review_conflict"}
    body = _verify(client, cid)
    assert body["ok"] is True and body["checked"] == 1


def _new_postgres_case(url: str) -> str:
    import secrets

    from vericlue_api.db.database import Database
    from vericlue_api.db.models import ReviewCaseRow, SessionRow

    suffix = secrets.token_hex(6)
    cid, sid = f"case_t{suffix}", f"ses_t{suffix}"
    database = Database(url)
    try:
        with database.sessions.begin() as db:
            db.add(SessionRow(session_id=sid, status="review", ever_review=True))
            db.flush()
            db.add(
                ReviewCaseRow(
                    case_id=cid,
                    session_id=sid,
                    payload={"scenario": "genuine", "results": {}, "media": [], "notes": []},
                )
            )
    finally:
        database.dispose()
    return cid


def test_postgres_concurrent_initial_and_decisions(monkeypatch):
    """Cùng kịch bản trên PostgreSQL thật (khóa hàng); bỏ qua nếu thiếu TEST_DATABASE_URL."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL enables the real PostgreSQL integration test")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    cid = _new_postgres_case(url)  # DB dùng chung giữa các lần chạy: luôn tạo ca riêng
    with TestClient(create_app()) as client:
        barrier = Barrier(2)

        def go(decision):
            barrier.wait(timeout=5)
            return _initial(client, cid, decision)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                f.result(timeout=15) for f in [pool.submit(go, d) for d in ("accept", "reject")]
            ]
        assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
        assert _verify(client, cid) == {**_verify(client, cid), "ok": True, "checked": 1}

        barrier2 = Barrier(2)

        def fin():
            barrier2.wait(timeout=5)
            return _final(client, cid)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=15) for f in [pool.submit(fin) for _ in range(2)]]
        assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
        body = _verify(client, cid)
        assert body["ok"] is True and body["checked"] == 2


def test_ai_suggestion_boundary_matches_router(monkeypatch):
    """Λ ≤ B là pass (cùng biên với bộ quyết định)."""
    from vericlue_api.services import review_store
    from vericlue_api.services.review_store import CaseRecord

    record = CaseRecord(
        case_id="c", session_id="s", priority="normal", scenario="genuine", results={}, media=[]
    )
    for p, expected in ((0.15, "pass"), (0.1500001, "review")):
        monkeypatch.setattr(review_store, "fused_prob", lambda *_a, _p=p: _p)
        assert record.ai_opinion(0.15).suggestion == expected
