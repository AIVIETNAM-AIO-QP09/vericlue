"""Real PostgreSQL migration/transaction tests (CI service or local Docker)."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError

from vericlue_api.core.config import get_settings
from vericlue_api.db.database import Database
from vericlue_api.db.models import DecisionRow, ModuleResultRow, ReviewEventRow, SessionRow
from vericlue_api.main import create_app


@pytest.fixture
def postgres(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL enables the real PostgreSQL integration test")
    assert url.startswith("postgresql"), "Integration tests require PostgreSQL"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    database = Database(url)
    yield database
    database.dispose()
    get_settings.cache_clear()


def test_postgres_migration_mock_flow_and_restart(postgres):
    assert {"sessions", "module_results", "decisions", "review_events", "forensic_jobs"} <= set(
        inspect(postgres.engine).get_table_names()
    )
    with TestClient(create_app()) as client:
        response = client.post("/v1/sessions")
        assert response.status_code == 200
        body = response.json()
        auth = {"Authorization": "Bearer " + body["token"]}
        sid = body["session_id"]
        assert (
            client.post(
                f"/v1/sessions/{sid}/media",
                headers=auth,
                files={"image": ("face.jpg", b"synthetic", "image/jpeg")},
            ).status_code
            == 200
        )
        assert client.post(f"/v1/sessions/{sid}/finalize", headers=auth).json() == {
            "status": "pass"
        }
    with postgres.sessions() as db:
        row = db.get(SessionRow, sid)
        assert row.status == "pass" and row.decided_at is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(ModuleResultRow)
                .where(ModuleResultRow.session_id == sid)
            )
            > 0
        )
        assert (
            db.scalar(
                select(func.count()).select_from(DecisionRow).where(DecisionRow.session_id == sid)
            )
            == 1
        )
    with TestClient(create_app()) as restarted:
        with restarted.app.state.vericlue.transaction() as state:
            assert state.sessions.get(sid).results
            assert state.sessions.get(sid).token == body["token"]
        assert (
            restarted.post(
                f"/v1/sessions/{sid}/signals",
                headers=auth,
                json={"color_events": [], "frame_times": []},
            ).status_code
            == 200
        )


def test_postgres_review_events_are_append_only(postgres):
    with TestClient(create_app()) as client:
        created = client.post("/v1/sessions", headers={"X-Mock-Scenario": "print"}).json()
        auth = {"Authorization": "Bearer " + created["token"]}
        sid = created["session_id"]
        assert client.post(f"/v1/sessions/{sid}/finalize", headers=auth).json() == {
            "status": "review"
        }
        cases = client.get("/v1/review/cases").json()["items"]
        case = next(item["case_id"] for item in cases if item["session_id"] == sid)
        assert (
            client.post(
                f"/v1/review/cases/{case}/initial", json={"decision": "reject", "note": "synthetic"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/v1/review/cases/{case}/decision",
                json={"decision": "reject", "reason_code": "TEST"},
            ).status_code
            == 200
        )
    with postgres.sessions() as db:
        events = db.scalars(
            select(ReviewEventRow).where(ReviewEventRow.case_id == case).order_by(ReviewEventRow.id)
        ).all()
        assert len(events) == 2 and events[1].prev_hash == events[0].hash
        identifier = events[0].id
    # Deliberate forbidden statements exist only in this negative DB-permission test.
    for statement in (
        "UPDATE review_events SET note='changed' WHERE id=:id",
        "DELETE FROM review_events WHERE id=:id",
    ):
        with pytest.raises(DBAPIError), postgres.engine.begin() as connection:
            connection.execute(text(statement), {"id": identifier})
    with postgres.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(ReviewEventRow)
                .where(ReviewEventRow.case_id == case)
            )
            == 2
        )
