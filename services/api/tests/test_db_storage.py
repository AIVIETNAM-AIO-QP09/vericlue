"""PLAT-05: migrations, restart persistence and media retention on isolated SQLite."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from conftest import staff_test_client
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.db.database import Database
from vericlue_api.db.models import (
    CleanupAuditRow,
    ForensicJobRow,
    ReviewCaseRow,
    ReviewEventRow,
    SessionRow,
)
from vericlue_api.main import create_app
from vericlue_api.services.session_store import SessionStore
from vericlue_api.services.storage import cleanup_expired

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "services/api"
NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)


def migrate(url):
    config = Config(str(API / "alembic.ini"))
    config.set_main_option("script_location", str(API / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture
def database(tmp_path):
    url = f"sqlite:///{(tmp_path / 'storage.sqlite').as_posix()}"
    migrate(url)
    db = Database(url)
    yield db
    db.engine.dispose()


def test_migration_creates_schema_and_is_repeatable(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migration.sqlite').as_posix()}"
    migrate(url)
    migrate(url)
    db = Database(url)
    try:
        assert {
            "sessions",
            "module_results",
            "decisions",
            "review_cases",
            "review_events",
            "forensic_jobs",
            "forensic_segments",
            "cleanup_audits",
        } <= set(inspect(db.engine).get_table_names())
    finally:
        db.engine.dispose()


def settings_for(tmp_path, **changes):
    return Settings(media_dir=str(tmp_path / "media"), **changes)


def media_file(settings, folder, name="face.jpg"):
    file = Path(settings.media_dir) / folder / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"synthetic test media")
    return file


def add_session(database, identifier, status, age, *, ever_review=False):
    with database.sessions.begin() as connection:
        connection.add(
            SessionRow(
                session_id=identifier,
                status=status,
                ever_review=ever_review,
                created_at=NOW - age,
                last_activity_at=NOW - age,
                decided_at=None if status == "incomplete" else NOW - age,
                media_deleted_at=None,
                payload={},
            )
        )


def test_pass_review_incomplete_ttls_and_forensic_default_protection(database, tmp_path):
    settings = settings_for(tmp_path)
    cases = [
        ("expired-pass", "pass", timedelta(hours=25), False, True),
        ("fresh-pass", "pass", timedelta(hours=23), False, False),
        ("expired-review", "review", timedelta(days=31), True, True),
        ("fresh-review", "review", timedelta(days=29), True, False),
        ("expired-incomplete", "incomplete", timedelta(hours=25), False, True),
        ("fresh-incomplete", "incomplete", timedelta(hours=23), False, False),
        ("review-later-pass", "pass", timedelta(days=2), True, False),
    ]
    paths = {}
    for identifier, status, age, ever_review, _expired in cases:
        add_session(database, identifier, status, age, ever_review=ever_review)
        if ever_review:
            with database.sessions.begin() as connection:
                connection.add(
                    ReviewCaseRow(
                        case_id=f"case-{identifier}",
                        session_id=identifier,
                        status="closed",
                        payload={},
                    )
                )
        paths[identifier] = media_file(settings, identifier)
    forensic = media_file(settings, "forensic/job-protected", "original.wav")
    with database.sessions.begin() as connection:
        connection.add(
            ForensicJobRow(
                job_id="job-protected",
                created_at=NOW - timedelta(days=90),
                source_path=str(forensic),
                payload={},
            )
        )
    audits = cleanup_expired(database, settings, now=NOW)
    assert audits
    for identifier, _, _, _, expired in cases:
        assert paths[identifier].exists() is (not expired)
    assert forensic.exists()
    with database.sessions() as connection:
        persisted = connection.scalars(select(CleanupAuditRow)).all()
        assert persisted
        for identifier, _, _, _, expired in cases:
            row = connection.get(SessionRow, identifier)
            assert (row.media_deleted_at is not None) is expired
    # Running twice neither removes protected media nor loses prior audit trail.
    cleanup_expired(database, settings, now=NOW)
    assert forensic.exists()
    with database.sessions() as connection:
        assert len(connection.scalars(select(CleanupAuditRow)).all()) >= len(persisted)


def test_cleanup_does_not_follow_directory_symlink(database, tmp_path):
    settings = settings_for(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    external_file = outside / "keep.jpg"
    external_file.write_bytes(b"protected outside bytes")
    root = Path(settings.media_dir)
    root.mkdir()
    try:
        (root / "expired").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Platform requires permission to create directory symlinks")
    add_session(database, "expired", "pass", timedelta(days=2))
    cleanup_expired(database, settings, now=NOW)
    assert external_file.read_bytes() == b"protected outside bytes"


def test_restart_keeps_session_media_signals_review_and_forensic(database, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", str(database.engine.url))
    get_settings.cache_clear()
    app = create_app()
    with staff_test_client(app) as client:
        body = client.post("/v1/sessions", headers={"X-Mock-Scenario": "print"}).json()
        sid = body["session_id"]
        headers = {"Authorization": f"Bearer {body['token']}"}
        assert (
            client.post(
                f"/v1/sessions/{sid}/media",
                headers=headers,
                files={"image": ("face.jpg", b"synthetic", "image/jpeg")},
            ).status_code
            == 200
        )
        signals = {
            "color_events": [{"index": 0, "rgb": "#ffcc73", "painted_at": 1234.5}],
            "frame_times": [{"capture_time": 1240.2, "presented_frames": 31, "media_time": 0.5}],
        }
        assert (
            client.post(f"/v1/sessions/{sid}/signals", headers=headers, json=signals).status_code
            == 200
        )
        assert client.post(f"/v1/sessions/{sid}/finalize", headers=headers).json() == {
            "status": "review"
        }
        case = next(
            item
            for item in client.get("/v1/review/cases").json()["items"]
            if item["session_id"] == sid
        )
        case_id = case["case_id"]
        assert (
            client.post(
                f"/v1/review/cases/{case_id}/initial", json={"decision": "reject"}
            ).status_code
            == 200
        )
        job = client.post(
            "/v1/forensic/jobs", files={"file": ("original.wav", b"original bytes", "audio/wav")}
        ).json()
        job_id = job["job_id"]
        report_before = client.get(f"/v1/forensic/jobs/{job_id}/report")
    with staff_test_client(create_app()) as restarted:
        with restarted.app.state.vericlue.transaction() as state:
            session = state.sessions.get(sid)
            assert session.signals["frame_times"][0]["presented_frames"] == 31
            assert session.results and session.images
            assert session.challenge.model_dump(mode="json", exclude_none=True) == body["challenge"]
            assert session.case_id == case_id
        assert restarted.get(f"/v1/review/cases/{case_id}/ai").status_code == 200
        assert restarted.post(f"/v1/sessions/{sid}/finalize", headers=headers).status_code == 409
        after = restarted.get(f"/v1/forensic/jobs/{job_id}/report")
        assert after.text == report_before.text
        assert (
            after.headers["X-VeriClue-Report-SHA256"]
            == report_before.headers["X-VeriClue-Report-SHA256"]
        )
    get_settings.cache_clear()


def test_audit_records_every_cleanup_run_with_files_and_reasons(database, tmp_path):
    settings = settings_for(tmp_path)
    add_session(database, "expired-pass", "pass", timedelta(hours=25))
    target = media_file(settings, "expired-pass")
    cleanup_expired(database, settings, now=NOW)
    cleanup_expired(database, settings, now=NOW)
    with database.sessions() as connection:
        audits = connection.scalars(select(CleanupAuditRow).order_by(CleanupAuditRow.id)).all()
        assert len(audits) == 2
        assert all(audit.reason == "media_cleanup" for audit in audits)
        assert str(target) in audits[0].files
        assert any(
            item["path"] == str(target) and item["reason"] == "pass_expired"
            for item in audits[0].details["deleted"]
        )
        assert audits[1].files == []
        assert audits[1].details["deleted"] == []
        assert audits[0].created_at is not None


def test_forensic_explicit_ttl_and_outside_path_protection(database, tmp_path):
    settings = settings_for(tmp_path, forensic_ttl_days=30)
    expired = media_file(settings, "forensic/job-expired", "original.wav")
    fresh = media_file(settings, "forensic/job-fresh", "original.wav")
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"outside media root must survive")
    with database.sessions.begin() as connection:
        for identifier, path, age in [
            ("job-expired", expired, 31),
            ("job-fresh", fresh, 29),
            ("job-outside", outside, 31),
        ]:
            connection.add(
                ForensicJobRow(
                    job_id=identifier,
                    created_at=NOW - timedelta(days=age),
                    source_path=str(path),
                    payload={},
                )
            )
    cleanup_expired(database, settings, now=NOW)
    assert not expired.exists()
    assert fresh.exists()
    assert outside.read_bytes() == b"outside media root must survive"
    with database.sessions() as connection:
        assert connection.get(ForensicJobRow, "job-expired").media_deleted_at is not None
        assert connection.get(ForensicJobRow, "job-fresh").media_deleted_at is None
        assert connection.get(ForensicJobRow, "job-outside").media_deleted_at is None
        audit = connection.scalars(select(CleanupAuditRow)).one()
        assert any(item["reason"] == "forensic_expired" for item in audit.details["deleted"])
        assert audit.details["errors"]


def test_incomplete_ttl_uses_last_activity_not_creation(database, tmp_path):
    settings = settings_for(tmp_path)
    add_session(database, "recently-active", "incomplete", timedelta(days=10))
    target = media_file(settings, "recently-active")
    with database.sessions.begin() as connection:
        connection.get(SessionRow, "recently-active").last_activity_at = NOW - timedelta(hours=1)
    cleanup_expired(database, settings, now=NOW)
    assert target.exists()


@pytest.mark.parametrize("status", ["deny", "recovery_required"])
def test_reauth_terminal_media_uses_incomplete_retention(database, tmp_path, status):
    settings = settings_for(tmp_path)
    add_session(database, "expired-reauth", status, timedelta(hours=25))
    add_session(database, "fresh-reauth", status, timedelta(hours=23))
    expired = media_file(settings, "expired-reauth")
    fresh = media_file(settings, "fresh-reauth")
    cleanup_expired(database, settings, now=NOW)
    assert not expired.exists() and fresh.exists()


def test_blank_forensic_ttl_is_disabled(monkeypatch):
    monkeypatch.setenv("FORENSIC_TTL_DAYS", "")
    assert Settings().forensic_ttl_days is None


@pytest.mark.parametrize(
    "operation", ["UPDATE review_events SET note='changed'", "DELETE FROM review_events"]
)
def test_review_events_reject_update_and_delete_at_database_layer(database, operation):
    add_session(database, "audit-session", "review", timedelta(days=1), ever_review=True)
    with database.sessions.begin() as connection:
        connection.add(ReviewCaseRow(case_id="audit-case", session_id="audit-session", payload={}))
        connection.flush()
        connection.add(
            ReviewEventRow(
                case_id="audit-case",
                action="initial",
                prev_hash="0" * 64,
                hash="a" * 64,
                payload={},
            )
        )
    with pytest.raises(DBAPIError, match="append-only"), database.engine.begin() as connection:
        connection.execute(text(operation))
    with database.sessions() as connection:
        events = connection.scalars(select(ReviewEventRow)).all()
        assert len(events) == 1
        assert events[0].hash == "a" * 64 and events[0].note is None


@pytest.mark.parametrize("status,ever_review", [("pass", False), ("review", True)])
def test_decided_ttl_starts_at_decision_not_creation(database, tmp_path, status, ever_review):
    settings = settings_for(tmp_path)
    add_session(database, "new-decision", status, timedelta(days=100), ever_review=ever_review)
    target = media_file(settings, "new-decision")
    with database.sessions.begin() as connection:
        connection.get(SessionRow, "new-decision").decided_at = NOW - timedelta(hours=1)
    cleanup_expired(database, settings, now=NOW)
    assert target.exists()
    with database.sessions() as connection:
        assert connection.get(SessionRow, "new-decision").media_deleted_at is None


def test_cleanup_logs_exactly_one_audit_line_per_call(database, tmp_path, caplog):
    settings = settings_for(tmp_path)
    with caplog.at_level("INFO", logger="vericlue_api.services.storage"):
        cleanup_expired(database, settings, now=NOW)
        cleanup_expired(database, settings, now=NOW)
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "vericlue_api.services.storage"
        and record.getMessage().startswith("media_cleanup_audit ")
    ]
    assert len(messages) == 2
    assert all('"created_at"' in message and '"deleted"' in message for message in messages)


def test_new_upload_resets_deleted_marker(client):
    created = client.post("/v1/sessions").json()
    identifier = created["session_id"]
    database = client.app.state.vericlue.database
    with database.sessions.begin() as connection:
        connection.get(SessionRow, identifier).media_deleted_at = NOW
    response = client.post(
        f"/v1/sessions/{identifier}/media",
        headers={"Authorization": f"Bearer {created['token']}"},
        files={"image": ("face.jpg", b"new media", "image/jpeg")},
    )
    assert response.status_code == 200
    with database.sessions() as connection:
        assert connection.get(SessionRow, identifier).media_deleted_at is None


def test_partial_cleanup_failure_still_audits_successfully_deleted_files(
    database, tmp_path, monkeypatch
):
    settings = settings_for(tmp_path)
    add_session(database, "partial-cleanup", "pass", timedelta(days=2))
    first = media_file(settings, "partial-cleanup", "a.jpg")
    second = media_file(settings, "partial-cleanup", "b.jpg")
    original_unlink = Path.unlink
    attempted = []

    def fail_after_one_success(path, *args, **kwargs):
        if path in (first, second):
            attempted.append(path)
            if len(attempted) == 2:
                raise OSError("synthetic second-file unlink failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_after_one_success)
    cleanup_expired(database, settings, now=NOW)
    assert len(attempted) == 2
    deleted, preserved = attempted
    assert not deleted.exists()
    assert preserved.exists()
    with database.sessions() as connection:
        audit = connection.scalars(select(CleanupAuditRow)).one()
        assert audit.files == [str(deleted)]
        assert audit.details["deleted"] == [{"path": str(deleted), "reason": "pass_expired"}]
        assert audit.details["errors"]
        assert "synthetic second-file unlink failure" in audit.details["errors"][0]["error"]
        assert connection.get(SessionRow, "partial-cleanup").media_deleted_at is None


def test_compose_database_password_special_characters_roundtrip():
    settings = Settings(
        database_host="db",
        database_port=5432,
        postgres_user="demo_user",
        postgres_password="p@ss:/#word",
        postgres_db="demo_db",
    )
    url = make_url(settings.database_url)
    assert url.password == "p@ss:/#word"
    assert url.username == "demo_user" and url.host == "db"
    assert url.database == "demo_db" and url.port == 5432


@pytest.mark.parametrize("host", [None, ""])
def test_native_database_url_is_preserved_without_compose_host(host):
    original = "sqlite:///native-database.sqlite"
    settings = Settings(
        database_host=host, database_url=original, postgres_password="irrelevant@secret"
    )
    assert settings.database_url == original


def test_database_commit_failure_returns_safe_503_and_rolls_back(client, monkeypatch):
    database = client.app.state.vericlue.database
    with database.sessions() as connection:
        before = connection.scalar(select(func.count()).select_from(SessionRow))

    def fail_save(_store):
        raise SQLAlchemyError("private-password=p@ss:/#word; SQL SELECT secret FROM hidden")

    monkeypatch.setattr(SessionStore, "save_all", fail_save)
    response = client.post("/v1/sessions")
    assert response.status_code == 503
    payload = response.json()
    assert set(payload) == {"error_code", "message"}
    assert payload["error_code"] == "storage_unavailable"
    assert payload["message"]
    assert "private-password" not in response.text
    assert "p@ss" not in response.text and "SELECT" not in response.text
    with database.sessions() as connection:
        after = connection.scalar(select(func.count()).select_from(SessionRow))
    assert after == before


@pytest.mark.parametrize(
    "case_status,closure_age,should_delete",
    [
        ("open", None, False),
        ("initial_decided", None, False),
        ("closed", timedelta(days=31), True),
        ("closed", timedelta(days=1), False),
    ],
)
def test_review_retention_starts_only_after_staff_closes_case(
    database, tmp_path, case_status, closure_age, should_delete
):
    settings = settings_for(tmp_path)
    add_session(database, "review-retention", "review", timedelta(days=40), ever_review=True)
    target = media_file(settings, "review-retention")
    with database.sessions.begin() as connection:
        row = connection.get(SessionRow, "review-retention")
        # Old AI timestamps must never start the retention clock for an open case.
        row.decided_at = NOW - timedelta(days=40) if closure_age is None else NOW - closure_age
        connection.add(
            ReviewCaseRow(
                case_id="retention-case", session_id=row.session_id, status=case_status, payload={}
            )
        )
    cleanup_expired(database, settings, now=NOW)
    assert target.exists() is (not should_delete)
    with database.sessions() as connection:
        assert (
            connection.get(SessionRow, "review-retention").media_deleted_at is not None
        ) is should_delete
