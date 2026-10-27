"""Real PostgreSQL migration/transaction tests (CI service or local Docker)."""

import base64
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from conftest import staff_test_client
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.core.session_tokens import token_digest
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


def test_postgres_credential_issue_rollback_and_parallel_retry(postgres, tmp_path, monkeypatch):
    from test_credential_issuance import authorize, offer, setup_credential

    from vericlue_api.db.models import CredentialIssuanceRow
    from vericlue_api.schemas.credential import CredentialIssueRequest
    from vericlue_api.services.credential_issuance import CredentialIssuance

    # PostgreSQL fixtures share the seeded review rows. Keep those plaintext;
    # enable encryption only after startup, for this test's own credential flow.
    monkeypatch.setenv("SESSION_PRIVACY", "false")
    monkeypatch.setenv("SESSION_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    get_settings.cache_clear()
    with staff_test_client(create_app()) as client:
        root = client.app.state.vericlue
        root.settings = root.settings.model_copy(update={"session_privacy": True})
        key, _, body, headers, calls = setup_credential(client, tmp_path, monkeypatch)
        request = authorize(client, body, headers, offer(), key)
        sid = body["session_id"]
        with pytest.raises(RuntimeError), root.transaction() as state:
            CredentialIssuance(state).issue(
                state.sessions.get(sid), CredentialIssueRequest.model_validate(request)
            )
            raise RuntimeError("synthetic rollback after BBS issuance")
        with root.database.sessions() as db:
            assert db.get(CredentialIssuanceRow, sid) is None
        calls.clear()
        ready = Barrier(2)

        def submit(_):
            ready.wait(timeout=10)
            return client.post(f"/v1/sessions/{sid}/credential", headers=headers, json=request)

        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(submit, range(2)))
        assert [r.status_code for r in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
        assert len(calls) == 1
        with root.database.sessions() as db:
            assert db.get(CredentialIssuanceRow, sid) is not None


def test_postgres_linked_report_checkpoint_rollback_and_parallel_exports(postgres, monkeypatch):
    """Native PostgreSQL JSON CAS/row locking, fake media analysis and real signatures."""
    from test_forensic_real import FakeSource, _face, _pipeline, _voice
    from test_review_audit_link import finalize_review, prepare_case, submit

    from vericlue_api.db.models import ForensicJobRow
    from vericlue_api.services import forensic_runner
    from vericlue_ml.common.result import Module

    monkeypatch.setenv("SESSION_PRIVACY", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(forensic_runner, "FileMediaSource", FakeSource)
    monkeypatch.setattr(
        forensic_runner,
        "build_pipeline",
        lambda root: _pipeline(
            {
                Module.FACE_DEEPFAKE: _face(),
                Module.VOICE_SPOOF: _voice(),
            }
        ),
    )
    with staff_test_client(create_app()) as client:
        cid, _ = prepare_case(client)
        root = client.app.state.vericlue
        monkeypatch.setattr(root.settings, "use_mock_models", False)
        response = submit(client, cid)
        assert response.status_code == 200, response.text
        jid = response.json()["job_id"]
        finalize_review(client, cid)
        with pytest.raises(RuntimeError), root.transaction() as state:
            assert state.forensic.report_job(jid).review_audit.event_count == 2
            raise RuntimeError("synthetic failed export transaction")
        with root.database.sessions() as db:
            assert db.get(ForensicJobRow, jid).payload["job"]["review_audit"]["event_count"] == 1
        ready = Barrier(2)

        def export(_):
            ready.wait(timeout=10)
            return client.get(f"/v1/forensic/jobs/{jid}/report")

        with ThreadPoolExecutor(2) as pool:
            reports = list(pool.map(export, range(2)))
        signer = root.settings.report_signer
        for report in reports:
            assert report.status_code == 200, report.text
            import hashlib

            assert signer.verify(
                hashlib.sha256(report.content).hexdigest(), report.headers["X-VeriClue-Signature"]
            )
        with root.database.sessions() as db:
            assert db.get(ForensicJobRow, jid).payload["job"]["review_audit"]["event_count"] == 2
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(ReviewEventRow)
                    .where(ReviewEventRow.case_id == cid)
                )
                == 2
            )


def test_signed_media_claim_rolls_back_with_failed_outer_request(postgres):
    from test_media_proof import IMAGE, VIDEO, create, send_face, sign

    from vericlue_api.db.models import MediaProofUseRow
    from vericlue_api.services.media_proof import verify_and_consume

    with staff_test_client(create_app()) as client:
        created, auth, key = create(client)
        proof = sign(client, created, key)
        root = client.app.state.vericlue
        with pytest.raises(RuntimeError), root.transaction() as state:
            session = state.sessions.get(created["session_id"])
            verify_and_consume(state.db, session, "face", proof, {"image": IMAGE, "video": VIDEO})
            raise RuntimeError("synthetic failed request after media claim")
        with root.database.sessions() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(MediaProofUseRow)
                    .where(MediaProofUseRow.session_id == created["session_id"])
                )
                == 0
            )
        assert send_face(client, created, auth, proof).status_code == 200


def test_media_nonce_unique_constraint_serializes_competing_claims(postgres):
    """Even stale readers outside SessionStore's row lock cannot claim a nonce twice."""
    from test_media_proof import IMAGE, VIDEO, create, sign

    from vericlue_api.core.errors import ApiError
    from vericlue_api.db.models import MediaProofUseRow
    from vericlue_api.services.media_proof import verify_and_consume

    with staff_test_client(create_app()) as client:
        created, _, key = create(client)
        proof = sign(client, created, key)
        root = client.app.state.vericlue
        with root.transaction() as state:
            snapshot = state.sessions.get(created["session_id"])
        ready = Barrier(2)

        def claim(_):
            ready.wait(timeout=10)
            try:
                with root.transaction() as state:
                    verify_and_consume(
                        state.db, snapshot, "face", proof, {"image": IMAGE, "video": VIDEO}
                    )
                return "accepted"
            except ApiError as exc:
                return exc.error_code

        with ThreadPoolExecutor(2) as pool:
            assert sorted(pool.map(claim, range(2))) == ["accepted", "media_not_accepted"]
        with root.database.sessions() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(MediaProofUseRow)
                    .where(MediaProofUseRow.session_id == created["session_id"])
                )
                == 1
            )


def test_account_l0_claim_and_recovery_races(postgres, monkeypatch):
    """Two L0 requests consume one challenge; two recoveries replace one old key once."""
    from pydantic import SecretStr
    from test_account_auth import new_key, recovery_ready, signed
    from test_accounts import prepared, real_settings

    from vericlue_api.core.errors import ApiError
    from vericlue_api.db.models import AccountRecoveryRow, DeviceProofUseRow
    from vericlue_api.schemas.session import CreateSessionRequest
    from vericlue_api.services.account_auth import AccountAuth, message
    from vericlue_api.services.accounts import AccountStore

    monkeypatch.setenv("SESSION_PRIVACY", "false")
    get_settings.cache_clear()
    with staff_test_client(create_app()) as client:
        root = client.app.state.vericlue
        with root.transaction() as state:
            record, template, continuity = prepared(state, id_hmac=secrets.token_hex(32))
            settings = real_settings(state).model_copy(
                update={
                    "session_privacy": True,
                    "session_master_key": SecretStr(
                        base64.b64encode(secrets.token_bytes(32)).decode()
                    ),
                }
            )
            store = AccountStore(settings, state.db)
            receipt = store.create(record, template, continuity=continuity)
            # Use a known real P-256 key, enrolled via the fully gated recovery fixture.
            key = new_key()
            receipt = store.recover(recovery_ready(state, receipt, key))
            created = state.flow.create(
                "genuine",
                CreateSessionRequest(
                    purpose="reauth",
                    nonce="postgres_race_synthetic_nonce",
                ),
            )
            session = state.sessions.get(created.session_id)
            AccountAuth(store).bind(session, receipt.account_id, receipt.device_id)
            signature = signed(key, message(session))
            sid = session.session_id

        ready = Barrier(2)

        def prove(_):
            ready.wait(timeout=10)
            try:
                with root.transaction() as state:
                    loaded = state.sessions.get(sid)
                    AccountAuth(AccountStore(settings, state.db)).verify(loaded, signature)
                return "accepted"
            except ApiError as exc:
                return exc.error_code

        with ThreadPoolExecutor(2) as pool:
            assert sorted(pool.map(prove, range(2))) == ["accepted", "recovery_required"]
        with root.transaction() as state:
            assert state.db.get(DeviceProofUseRow, sid) is not None
            first = recovery_ready(state, receipt, new_key()).session_id
            second = recovery_ready(state, receipt, new_key()).session_id
        ready = Barrier(2)

        def recover(recovery_sid):
            ready.wait(timeout=10)
            try:
                with root.transaction() as state:
                    loaded = state.sessions.get(recovery_sid)
                    AccountStore(settings, state.db).recover(loaded)
                return "accepted"
            except ApiError as exc:
                return exc.error_code

        with ThreadPoolExecutor(2) as pool:
            assert sorted(pool.map(recover, [first, second])) == [
                "accepted",
                "enrollment_not_available",
            ]
        with root.transaction() as state:
            rows = list(
                state.db.scalars(
                    select(AccountRecoveryRow).where(
                        AccountRecoveryRow.previous_device_id == receipt.device_id,
                    )
                )
            )
            assert len(rows) == 1
            assert state.db.get(SessionRow, sid).status == "incomplete"


def test_account_duplicate_identity_race(postgres, monkeypatch):
    """Two different locked sessions must not enroll the same live identity."""
    from pydantic import SecretStr
    from test_accounts import prepared, real_settings

    from vericlue_api.core.errors import ApiError
    from vericlue_api.db.models import AccountRow
    from vericlue_api.services.accounts import AccountStore

    # This fixture shares PostgreSQL's demo review rows with other test modules.
    # Keep those synthetic rows plaintext; only the account under test is encrypted.
    monkeypatch.setenv("SESSION_PRIVACY", "false")
    get_settings.cache_clear()
    identity_hmac = secrets.token_hex(32)
    with staff_test_client(create_app()) as client:
        root = client.app.state.vericlue
        with root.transaction() as state:
            first = prepared(state, id_hmac=identity_hmac)
            second = prepared(state, id_hmac=identity_hmac)
            settings = real_settings(state).model_copy(
                update={
                    "session_privacy": True,
                    "session_master_key": SecretStr(
                        base64.b64encode(secrets.token_bytes(32)).decode()
                    ),
                }
            )
        ready = Barrier(2)

        def enroll(record):
            session, template, continuity = record
            try:
                with root.transaction() as state:
                    loaded = state.sessions.get(session.session_id)
                    ready.wait(timeout=10)
                    AccountStore(settings, state.db).create(loaded, template, continuity=continuity)
                return "created"
            except ApiError as exc:
                return exc.error_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(enroll, [first, second]))
        assert sorted(results) == ["created", "enrollment_not_available"]
        with postgres.sessions() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(AccountRow)
                    .where(AccountRow.id_number_hmac == identity_hmac)
                )
                == 1
            )


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
    with staff_test_client(create_app()) as client:
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
    with staff_test_client(create_app()) as restarted:
        with restarted.app.state.vericlue.transaction() as state:
            assert state.sessions.get(sid).results
            assert state.sessions.get(sid).token == ""
            assert state.sessions.get(sid).token_hash == token_digest(body["token"])
        assert (
            restarted.post(
                f"/v1/sessions/{sid}/signals",
                headers=auth,
                json={"color_events": [], "frame_times": []},
            ).status_code
            == 409
        )


def test_postgres_review_events_are_append_only(postgres):
    with staff_test_client(create_app()) as client:
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
                json={"decision": "reject", "reason_code": "SPOOF_CONFIRMED"},
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
    with staff_test_client(create_app()) as client:
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
    with staff_test_client(create_app()) as client:
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
