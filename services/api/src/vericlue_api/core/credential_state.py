"""Verifier-only transactions; never start models or load session/issuer private keys."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_credential_db(request: Request) -> Iterator[Session]:
    root = request.app.state.vericlue
    with root.database.sessions.begin() as db:
        if db.bind.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        elif db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT set_config('lock_timeout', :timeout, true)"),
                {"timeout": f"{max(1, round(root.settings.db_lock_timeout_seconds * 1000))}ms"},
            )
        yield db
