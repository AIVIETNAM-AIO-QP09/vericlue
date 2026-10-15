"""Request-scoped transactions; import/create_app never opens a DB connection."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock

from fastapi import Request
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.config import Settings
from vericlue_api.db.database import Database
from vericlue_api.services.forensic_service import ForensicStore
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_flow import SessionFlow
from vericlue_api.services.session_store import SessionStore


@dataclass
class AppState:
    settings: Settings
    db: DBSession
    sessions: SessionStore = field(init=False)
    reviews: ReviewStore = field(init=False)
    forensic: ForensicStore = field(init=False)
    flow: SessionFlow = field(init=False)

    def __post_init__(self) -> None:
        self.sessions = SessionStore(self.db)
        self.reviews = ReviewStore(self.db)
        self.forensic = ForensicStore(
            self.settings.provisional_threshold_b,
            self.settings.provisional_threshold_a,
            self.db,
            self.settings.media_dir,
        )
        self.flow = SessionFlow(self.settings, self.sessions, self.reviews)


class ApplicationState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_url)
        self._initialized = False
        self._initializing = Lock()

    @contextmanager
    def transaction(self) -> Iterator[AppState]:
        with self.database.sessions.begin() as db:
            state = AppState(self.settings, db)
            yield state
            state.sessions.save_all()
            state.reviews.save_all()
            db.flush()

    def initialize(self) -> None:
        with self._initializing:
            if self._initialized:
                return
            with self.transaction() as state:
                if self.settings.use_mock_models:
                    state.reviews.seed_demo()
                else:
                    from sqlalchemy import select

                    from vericlue_api.db.models import SessionRow

                    state.db.execute(select(SessionRow.session_id).limit(1))
            self._initialized = True


def get_state(request: Request) -> Iterator[AppState]:
    root = request.app.state.vericlue
    root.initialize()
    with root.transaction() as state:
        yield state
