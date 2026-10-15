"""Real PostgreSQL migration/transaction tests (CI service or local Docker)."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.db.database import Database
from vericlue_api.db.models import (
    DecisionRow,
    ModuleResultRow,
    ReviewCaseRow,
    ReviewEventRow,
    SessionRow,
)
from vericlue_api.main import create_app
from vericlue_api.services import storage


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
    monkeypatch.setenv("PGOPTIONS", "-c lock_timeout=3000 -c statement_timeout=10000")
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


def test_postgres_concurrent_finalize_creates_exactly_one_review_case(postgres):
    with TestClient(create_app()) as client:
        created = client.post("/v1/sessions", headers={"X-Mock-Scenario": "print"}).json()
        sid = created["session_id"]
        barrier = Barrier(2)

        def finalize_once():
            barrier.wait(timeout=5)
            return client.post(
                f"/v1/sessions/{sid}/finalize",
                headers={"Authorization": "Bearer " + created["token"]},
            )

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(finalize_once) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        assert sorted(response.status_code for response in results) == [200, 409]
        accepted = next(response for response in results if response.status_code == 200)
        rejected = next(response for response in results if response.status_code == 409)
        assert accepted.json() == {"status": "review"}
        assert rejected.json()["error_code"] == "session_closed"
        assert all(response.json().get("status") != "pass" for response in results)
    with postgres.sessions() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(ReviewCaseRow)
                .where(ReviewCaseRow.session_id == sid)
            )
            == 1
        )


def test_postgres_cleanup_skips_locked_expired_and_does_not_lock_fresh_or_open(
    postgres, tmp_path, monkeypatch
):
    now = datetime.now(UTC)
    prefix = "locking_" + uuid4().hex
    identifiers = {kind: f"{prefix}_{kind}" for kind in ("locked", "expired", "fresh", "open")}
    settings = Settings(media_dir=str(tmp_path / "lock-media"))
    paths = {}
    with postgres.sessions.begin() as connection:
        for kind, sid in identifiers.items():
            age = timedelta(hours=1) if kind == "fresh" else timedelta(days=40)
            connection.add(
                SessionRow(
                    session_id=sid,
                    status="review" if kind == "open" else "pass",
                    ever_review=kind == "open",
                    created_at=now - age,
                    last_activity_at=now - age,
                    decided_at=now - age,
                    payload={},
                )
            )
            target = Path(settings.media_dir) / sid / "face.jpg"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"synthetic")
            paths[kind] = target
        connection.flush()
        connection.add(
            ReviewCaseRow(
                case_id=prefix + "_case",
                session_id=identifiers["open"],
                status="open",
                payload={"scenario": "print", "results": {}, "media": [], "notes": []},
            )
        )
    entered, release = Event(), Event()
    original_delete = storage._delete_folder

    def pause_expired(folder, *args, **kwargs):
        if folder.name == identifiers["expired"]:
            entered.set()
            assert release.wait(timeout=10), "test failed to release cleanup"
        return original_delete(folder, *args, **kwargs)

    monkeypatch.setattr(storage, "_delete_folder", pause_expired)
    with postgres.sessions.begin() as locker:
        locker.scalar(
            select(SessionRow)
            .where(SessionRow.session_id == identifiers["locked"])
            .with_for_update()
        )
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(storage.cleanup_expired, postgres, settings, now=now)
            try:
                assert entered.wait(timeout=5), (
                    "cleanup blocked on an already locked expired session"
                )
                with postgres.sessions.begin() as probe:
                    for kind in ("fresh", "open"):
                        row = probe.scalar(
                            select(SessionRow)
                            .where(SessionRow.session_id == identifiers[kind])
                            .with_for_update(nowait=True)
                        )
                        assert row is not None
            finally:
                release.set()
            future.result(timeout=10)
    assert paths["locked"].exists()
    assert not paths["expired"].exists()
    assert paths["fresh"].exists() and paths["open"].exists()


def test_postgres_review_list_does_not_lock_cases(postgres):
    with TestClient(create_app()) as client:
        cases = client.get("/v1/review/cases").json()["items"]
        assert cases
        with postgres.sessions.begin() as locked:
            locked.scalar(
                select(ReviewCaseRow)
                .where(ReviewCaseRow.case_id == cases[0]["case_id"])
                .with_for_update()
            )
            with ThreadPoolExecutor(max_workers=1) as worker:
                result = worker.submit(client.get, "/v1/review/cases").result(timeout=5)
            assert result.status_code == 200
