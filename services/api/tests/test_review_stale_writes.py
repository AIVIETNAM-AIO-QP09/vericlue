"""Force stale-read interleavings; never depend on thread scheduling or sleep."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import DecisionRow, ReviewCaseRow, SessionRow
from vericlue_api.main import create_app
from vericlue_api.services.review_store import ReviewStore


def submit(client, cid, action, decision, note=None):
    suffix = "initial" if action == "initial" else "decision"
    body = {"decision": decision}
    if action == "final":
        body["reason_code"] = "OTHER"
        body["note"] = f"Quyết định {decision}"
    if note is not None:
        body["note"] = note
    return client.post(f"/v1/review/cases/{cid}/{suffix}", json=body)


def case_id(client):
    return client.get("/v1/review/cases").json()["items"][0]["case_id"]


def decision_state(client, cid):
    database = client.app.state.vericlue.database
    with database.sessions() as db:
        row = db.get(ReviewCaseRow, cid)
        session = db.get(SessionRow, row.session_id)
        return (
            db.scalar(
                select(func.count())
                .select_from(DecisionRow)
                .where(DecisionRow.session_id == row.session_id)
            ),
            session.decided_at,
        )


@pytest.mark.parametrize("action", ["initial", "final"])
@pytest.mark.parametrize("stale_decision", ["accept", "reject"])
def test_stale_request_after_other_app_commit_cannot_append_duplicate(
    client, monkeypatch, action, stale_decision
):
    cid = case_id(client)
    if action == "final":
        assert submit(client, cid, "initial", "accept").status_code == 200
    loaded, resume = Event(), Event()
    original = ReviewStore.record_event

    def hold_stale(self, record, event_action, decision, **kwargs):
        if kwargs.get("note") == "Yêu cầu đọc trạng thái cũ":
            # Router has already accepted the stale initial/final fields in this request.
            loaded.set()
            assert resume.wait(10), "winner did not finish"
        return original(self, record, event_action, decision, **kwargs)

    monkeypatch.setattr(ReviewStore, "record_event", hold_stale)
    # Independent app/connection: an application-local mutex cannot provide DB semantics.
    with TestClient(create_app()) as other, ThreadPoolExecutor(max_workers=1) as pool:
        loser = pool.submit(
            submit, client, cid, action, stale_decision, "Yêu cầu đọc trạng thái cũ"
        )
        try:
            assert loaded.wait(10), "loser did not read the old case"
            winner = submit(other, cid, action, "accept")
            assert winner.status_code == 200, winner.text
        finally:
            resume.set()
        rejected = loser.result(timeout=15)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error_code"] == "review_conflict"
    case = client.get(f"/v1/review/cases/{cid}").json()
    key = "initial_decision" if action == "initial" else "final_decision"
    assert case[key] == "accept"
    assert [event["action"] for event in case["history"]] == (
        ["initial"] if action == "initial" else ["initial", "final"]
    )
    check = client.get(f"/v1/review/cases/{cid}/audit/verify").json()
    assert check["ok"] is True and check["checked"] == (1 if action == "initial" else 2)
    count, decided_at = decision_state(client, cid)
    assert count == (0 if action == "initial" else 1)
    assert (decided_at is not None) == (action == "final")


def test_simultaneous_final_decisions_have_one_winner_and_one_session_decision(client):
    cid = case_id(client)
    assert submit(client, cid, "initial", "accept").status_code == 200
    barrier = Barrier(4)

    def go(decision):
        barrier.wait(timeout=10)
        return decision, submit(client, cid, "final", decision)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(go, decision) for decision in ("accept", "reject") * 2]
        outcomes = [future.result(timeout=15) for future in futures]
    assert sorted(response.status_code for _, response in outcomes) == [200, 409, 409, 409]
    winner = next(decision for decision, response in outcomes if response.status_code == 200)
    case = client.get(f"/v1/review/cases/{cid}").json()
    assert case["status"] == "closed" and case["final_decision"] == winner
    count, decided_at = decision_state(client, cid)
    assert count == 1 and decided_at is not None
    check = client.get(f"/v1/review/cases/{cid}/audit/verify").json()
    assert check["ok"] is True and check["checked"] == 2


@pytest.mark.parametrize("action", ["initial", "final"])
def test_failure_after_event_insert_rolls_back_transition_and_all_side_effects(
    client, monkeypatch, action
):
    cid = case_id(client)
    if action == "final":
        assert submit(client, cid, "initial", "accept").status_code == 200
    original = ReviewStore.record_event

    def fail_after_insert(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise ApiError(503, "storage_unavailable", "Lỗi lưu dữ liệu thử nghiệm.")

    with monkeypatch.context() as patch:
        patch.setattr(ReviewStore, "record_event", fail_after_insert)
        response = submit(client, cid, action, "reject")
    assert response.status_code == 503
    case = client.get(f"/v1/review/cases/{cid}").json()
    assert case["status"] == ("open" if action == "initial" else "initial_decided")
    assert case["initial_decision"] == (None if action == "initial" else "accept")
    assert case["final_decision"] is None
    assert len(case["history"]) == (0 if action == "initial" else 1)
    assert decision_state(client, cid) == (0, None)
    # Rollback releases the right to make this decision; the next request may succeed.
    assert submit(client, cid, action, "accept").status_code == 200
    check = client.get(f"/v1/review/cases/{cid}/audit/verify").json()
    assert check["ok"] is True and check["checked"] == (1 if action == "initial" else 2)
