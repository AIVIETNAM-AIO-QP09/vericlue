"""Migration 0002: UNIQUE(case_id, prev_hash) trên review_events (REV-01)."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from vericlue_api.services.audit_log import GENESIS_HASH, ChainEvent, compute_hash, verify_chain

INDEX = "uq_review_events_case_prev_hash"


def _config(url: str) -> Config:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _insert_event(conn, case_id: str, prev: str, n: int) -> str:
    payload = f'{{"n":{n}}}'
    digest = compute_hash(prev, {"n": n})
    conn.execute(
        text(
            "INSERT INTO review_events (case_id, actor, action, prev_hash, hash, payload, created_at)"
            " VALUES (:c, 'staff-unverified', 'initial', :p, :h, :pl, '2026-10-16 00:00:00')"
        ),
        {"c": case_id, "p": prev, "h": digest, "pl": payload},
    )
    return digest


@pytest.fixture
def url(tmp_path):
    return f"sqlite:///{tmp_path / 'm.db'}"


def _make_case(engine, case_id: str) -> None:
    from sqlalchemy.orm import Session

    from vericlue_api.db.models import ReviewCaseRow, SessionRow

    with Session(engine) as db, db.begin():
        db.add(SessionRow(session_id=f"ses_{case_id}", status="review", ever_review=True))
        db.flush()
        db.add(ReviewCaseRow(case_id=case_id, session_id=f"ses_{case_id}"))


def test_index_exists_and_blocks_duplicate_prev_hash(url):
    command.upgrade(_config(url), "head")
    engine = create_engine(url)
    _make_case(engine, "case_a")
    names = {i["name"] for i in inspect(engine).get_indexes("review_events")}
    assert INDEX in names
    with engine.begin() as conn:
        _insert_event(conn, "case_a", GENESIS_HASH, 1)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _insert_event(conn, "case_a", GENESIS_HASH, 2)  # cùng điểm nối genesis


def test_other_case_may_use_genesis(url):
    command.upgrade(_config(url), "head")
    engine = create_engine(url)
    _make_case(engine, "case_a")
    _make_case(engine, "case_b")
    with engine.begin() as conn:
        _insert_event(conn, "case_a", GENESIS_HASH, 1)
        _insert_event(conn, "case_b", GENESIS_HASH, 2)


def test_upgrade_keeps_valid_old_chain_and_downgrade_works(url):
    config = _config(url)
    command.upgrade(config, "0001_storage")
    engine = create_engine(url)
    _make_case(engine, "case_old")
    with engine.begin() as conn:
        h1 = _insert_event(conn, "case_old", GENESIS_HASH, 1)
        _insert_event(conn, "case_old", h1, 2)

    command.upgrade(config, "head")  # dữ liệu cũ hợp lệ không vi phạm UNIQUE
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT prev_hash, hash, payload FROM review_events ORDER BY id")
        ).all()
    assert len(rows) == 2

    command.downgrade(config, "0001_storage")
    assert INDEX not in {i["name"] for i in inspect(engine).get_indexes("review_events")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM review_events")).scalar() == 2
        # trigger chỉ-ghi-thêm vẫn còn sau upgrade/downgrade
        with pytest.raises(Exception, match="append-only"):
            conn.execute(text("DELETE FROM review_events"))
    command.upgrade(config, "head")


def test_old_chain_still_verifies_after_upgrade(url):
    config = _config(url)
    command.upgrade(config, "0001_storage")
    engine = create_engine(url)
    _make_case(engine, "case_old")
    with engine.begin() as conn:
        h1 = _insert_event(conn, "case_old", GENESIS_HASH, 1)
        _insert_event(conn, "case_old", h1, 2)
    command.upgrade(config, "head")
    import json

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT prev_hash, hash, payload FROM review_events ORDER BY id")
        ).all()
    events = [ChainEvent(r[0], r[1], json.loads(r[2])) for r in rows]
    assert verify_chain(events).ok
