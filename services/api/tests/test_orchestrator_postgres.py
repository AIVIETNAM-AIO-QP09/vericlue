"""PLAT-08: real PostgreSQL row-lock budget for finalize and voice requests."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from synthetic_images import synthetic_image

from vericlue_api.core.config import get_settings
from vericlue_api.db.database import Database
from vericlue_api.db.models import DecisionRow, ModuleResultRow, SessionRow
from vericlue_api.main import create_app


@pytest.fixture
def locked_request_postgres(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL enables PostgreSQL orchestrator lock tests")
    assert url.startswith("postgresql"), "Row-lock tests require PostgreSQL"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_HOST", "")
    monkeypatch.setenv("DB_LOCK_TIMEOUT_SECONDS", "0.1")
    # A safety bound for regressions: this must not supply the requested 100 ms budget.
    monkeypatch.setenv("PGOPTIONS", "-c statement_timeout=3000")
    get_settings.cache_clear()
    database = Database(url)
    try:
        yield database
    finally:
        database.dispose()
        get_settings.cache_clear()


def snapshot(database, session_id):
    with database.sessions() as db:
        row = db.get(SessionRow, session_id)
        counts = tuple(
            db.scalar(select(func.count()).select_from(model).where(model.session_id == session_id))
            for model in (ModuleResultRow, DecisionRow)
        )
        return row.status, row.last_activity_at, row.payload, counts


@pytest.mark.parametrize("step", ["finalize", "voice"])
def test_locked_session_returns_storage_busy_without_mutation(locked_request_postgres, step):
    database = locked_request_postgres
    with TestClient(create_app()) as client:
        created = client.post("/v1/sessions", headers={"X-Mock-Scenario": "voice_clone"})
        assert created.status_code == 200
        body = created.json()
        sid = body["session_id"]
        auth = {"Authorization": "Bearer " + body["token"]}
        assert (
            client.post(
                f"/v1/sessions/{sid}/media",
                headers=auth,
                files={"image": ("face.jpg", synthetic_image(b"synthetic-face"), "image/jpeg")},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/v1/sessions/{sid}/signals",
                headers=auth,
                json={"color_events": [], "frame_times": []},
            ).status_code
            == 200
        )
        if step == "voice":
            challenge = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
            assert challenge.status_code == 200
            assert challenge.json()["status"] == "voice_challenge"
            assert challenge.json()["voice_prompt"]
        before = snapshot(database, sid)
        folder = Path(client.app.state.vericlue.settings.media_dir) / sid
        files_before = {
            str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob("*")
            if path.is_file()
        }
        locker = database.engine.connect()
        workers = ThreadPoolExecutor(max_workers=2)
        try:
            locker.execute(
                select(SessionRow.session_id).where(SessionRow.session_id == sid).with_for_update()
            )
            # This lock remains held until after both HTTP responses have completed.
            request_kwargs = {"headers": auth}
            if step == "voice":
                request_kwargs["files"] = {"audio": ("voice.wav", b"synthetic-audio", "audio/wav")}
            started = perf_counter()
            pending = workers.submit(client.post, f"/v1/sessions/{sid}/{step}", **request_kwargs)
            health = workers.submit(client.get, "/healthz")
            assert health.result(timeout=1).status_code == 200
            response = pending.result(timeout=2)
            assert perf_counter() - started < 1.5, "100 ms lock timeout was not applied"
            assert response.status_code == 503
            payload = response.json()
            assert set(payload) == {"error_code", "message"}
            assert payload["error_code"] == "storage_busy"
            assert isinstance(payload["message"], str) and payload["message"]
            for private in (
                body["token"],
                sid,
                "SELECT",
                "FOR UPDATE",
                "psycopg",
                "sqlalchemy",
                "postgresql",
            ):
                assert private not in response.text
            assert "pass" not in payload.values()
        finally:
            locker.rollback()
            locker.close()
            workers.shutdown(wait=True, cancel_futures=True)
        assert snapshot(database, sid) == before
        files_after = {
            str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob("*")
            if path.is_file()
        }
        assert files_after == files_before
        if step == "voice":
            assert not (folder / "voice_audio.wav").exists()
