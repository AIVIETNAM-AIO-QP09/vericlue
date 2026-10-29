"""SEC-06 uses only synthetic images and an isolated migrated test database."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from test_session_privacy import image_bytes, start
from test_session_privacy import private_client as private_client
from test_signed_result_api import configure

from vericlue_api.core import retention
from vericlue_api.core.retention import session_retention_deadline
from vericlue_api.db.models import ReviewCaseRow, SessionKeyRow, SessionRow, utcnow
from vericlue_api.services.storage import cleanup_expired


@pytest.fixture(autouse=True)
def ekyc_mode(monkeypatch):
    monkeypatch.setenv("PRODUCT_MODE", "ekyc")
    monkeypatch.setenv("MEDIA_TTL_UNVERIFIED_HOURS", "24")


def upload(client, *, scenario="genuine"):
    sid, auth = start(client, scenario)
    response = client.post(
        f"/v1/sessions/{sid}/media",
        headers=auth,
        files={"image": ("synthetic.jpg", image_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    return sid, auth


def test_unverified_is_terminal_without_creating_staff_case(private_client, tmp_path):
    sid, auth = upload(private_client, scenario="print")
    r = private_client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "review", r.text
    root = private_client.app.state.vericlue
    with root.database.sessions() as db:
        row = db.get(SessionRow, sid)
        assert row.status == "review" and row.ever_review
        assert row.decided_at is not None
        assert db.scalar(select(ReviewCaseRow).where(ReviewCaseRow.session_id == sid)) is None
    assert private_client.post(f"/v1/sessions/{sid}/challenge", headers=auth).status_code == 409
    configure(private_client, tmp_path)
    assert private_client.get(f"/v1/sessions/{sid}/result", headers=auth).status_code == 409
    assert private_client.post(f"/v1/sessions/{sid}/voice", headers=auth).status_code != 200


def test_review_is_deleted_at_finite_deadline_without_staff_close(private_client):
    sid, auth = upload(private_client, scenario="print")
    assert private_client.post(f"/v1/sessions/{sid}/finalize", headers=auth).status_code == 200
    root = private_client.app.state.vericlue
    with root.database.sessions() as db:
        deadline = session_retention_deadline(root.settings, db.get(SessionRow, sid))
        assert deadline is not None
    cleanup_expired(root.database, root.settings, now=deadline - timedelta(seconds=1))
    assert (Path(root.settings.media_dir) / sid).exists()
    cleanup_expired(root.database, root.settings, now=deadline)
    with root.database.sessions() as db:
        assert db.get(SessionRow, sid).media_deleted_at is not None
        assert db.get(SessionKeyRow, sid).wrapped_key is None
        assert db.get(SessionRow, sid).status == "review"
    assert not (Path(root.settings.media_dir) / sid).exists()


def test_old_open_review_is_bounded_when_ekyc_mode_is_selected(private_client):
    sid, auth = upload(private_client, scenario="print")
    assert private_client.post(f"/v1/sessions/{sid}/finalize", headers=auth).status_code == 200
    root = private_client.app.state.vericlue
    # A pre-existing review from tools mode can have no final-decision timestamp.
    with root.database.sessions.begin() as db:
        row = db.get(SessionRow, sid)
        row.decided_at = None
        row.created_at = utcnow() - timedelta(days=90)
        row.last_activity_at = utcnow()
        db.add(
            ReviewCaseRow(
                case_id="case_legacy_" + sid,
                session_id=sid,
                status="open",
                payload={},
            )
        )
    cleanup_expired(root.database, root.settings)
    with root.database.sessions() as db:
        assert db.get(SessionKeyRow, sid).wrapped_key is None


def test_expired_snapshot_is_denied_before_cleanup_and_polling_cannot_extend(private_client):
    sid, auth = upload(private_client)
    root = private_client.app.state.vericlue
    with root.database.sessions.begin() as db:
        row = db.get(SessionRow, sid)
        row.created_at = utcnow() - timedelta(days=2)
        row.last_activity_at = utcnow()
        deadline = session_retention_deadline(root.settings, row)
    # Bearer is still fresh in this controlled fixture; retention is a separate check.
    r = private_client.post(f"/v1/sessions/{sid}/challenge", headers=auth)
    assert r.status_code == 410 and r.json()["error_code"] == "data_expired", r.text
    with root.database.sessions() as db:
        row = db.get(SessionRow, sid)
        assert session_retention_deadline(root.settings, row) == deadline
        assert row.media_deleted_at is None  # physical cleanup has not run
        assert db.get(SessionKeyRow, sid).wrapped_key is not None


def test_future_tools_routes_are_not_exposed_in_ekyc_mode(private_client):
    assert private_client.get("/v1/review/cases").status_code == 404
    assert private_client.post("/v1/forensic/jobs", content=b"not multipart").status_code == 404
    paths = private_client.get("/openapi.json").json()["paths"]
    assert not any(p.startswith(("/v1/review", "/v1/forensic")) for p in paths)


def test_inference_finishing_after_retention_cannot_renew_or_commit_pass(
    private_client, monkeypatch
):
    sid, auth = upload(private_client)
    root = private_client.app.state.vericlue
    with root.database.sessions() as db:
        initial = db.get(SessionRow, sid)
        deadline = session_retention_deadline(root.settings, initial)
        snapshot = initial.payload
    original = root.orchestrator.run

    def finish_after_deadline(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(retention, "utcnow", lambda: deadline + timedelta(seconds=1))
        return result

    monkeypatch.setattr(root.orchestrator, "run", finish_after_deadline)
    result = private_client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
    assert result.status_code == 410 and result.json()["error_code"] == "data_expired", result.text
    with root.database.sessions() as db:
        row = db.get(SessionRow, sid)
        assert row.status == "incomplete" and row.decided_at is None
        assert row.payload == snapshot


def test_pass_and_unverified_retention_use_their_own_configured_windows(private_client):
    sid, auth = upload(private_client)
    root = private_client.app.state.vericlue
    settings = root.settings.model_copy(
        update={"media_ttl_pass_hours": 48, "media_ttl_unverified_hours": 24}
    )
    with root.database.sessions() as db:
        row = db.get(SessionRow, sid)
        assert row.decided_at is None
        row.status = "pass"
        pass_deadline = session_retention_deadline(settings, row)
        row.status = "incomplete"
        other_deadline = session_retention_deadline(settings, row)
        assert pass_deadline - other_deadline == timedelta(hours=24)
