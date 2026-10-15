"""Request-scoped transactions; import/create_app never opens a DB connection."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial
from threading import Lock
from time import perf_counter

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.config import Settings
from vericlue_api.db.database import Database
from vericlue_api.services.forensic_service import ForensicStore
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_flow import SessionFlow
from vericlue_api.services.session_store import SessionStore


@dataclass
class AppState:
    settings: Settings
    db: DBSession
    orchestrator: Orchestrator
    inference_deadline: float | None = None
    sessions: SessionStore = field(init=False)
    reviews: ReviewStore = field(init=False)
    forensic: ForensicStore = field(init=False)
    flow: SessionFlow = field(init=False)

    def __post_init__(self) -> None:
        runner = partial(self.orchestrator.run, deadline=self.inference_deadline)
        self.sessions = SessionStore(self.db)
        self.reviews = ReviewStore(self.db, runner=runner)
        self.forensic = ForensicStore(
            self.settings.provisional_threshold_b,
            self.settings.provisional_threshold_a,
            self.db,
            self.settings.media_dir,
            runner=runner,
        )
        self.flow = SessionFlow(self.settings, self.sessions, self.reviews, runner=runner)


class ApplicationState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_url)
        self.orchestrator = Orchestrator(settings)
        self._initialized = False
        self._initializing = Lock()

    @contextmanager
    def transaction(
        self, *, lock_timeout_seconds: float | None = None, inference_deadline: float | None = None
    ) -> Iterator[AppState]:
        with self.database.sessions.begin() as db:
            if lock_timeout_seconds is not None and db.bind.dialect.name == "postgresql":
                db.execute(
                    text("SELECT set_config('lock_timeout', :timeout, true)"),
                    {"timeout": f"{max(1, round(lock_timeout_seconds * 1000))}ms"},
                )
            state = AppState(self.settings, db, self.orchestrator, inference_deadline)
            yield state
            state.sessions.save_all()
            state.reviews.save_all()
            db.flush()

    def initialize(self) -> None:
        with self._initializing:
            if self._initialized:
                return
            self.orchestrator.start()
            with self.transaction() as state:
                if self.settings.use_mock_models:
                    state.reviews.seed_demo()
                else:
                    from sqlalchemy import select

                    from vericlue_api.db.models import SessionRow

                    state.db.execute(select(SessionRow.session_id).limit(1))
            self._initialized = True


def get_state(request: Request) -> Iterator[AppState]:
    # Leave 200 ms for policy/flush/commit/serialization under a healthy DB.
    inference_deadline = perf_counter() + 4.8
    root = request.app.state.vericlue
    root.initialize()
    route = request.scope.get("route")
    guarded = request.method == "POST" and getattr(route, "path", "") in {
        "/v1/sessions/{session_id}/finalize",
        "/v1/sessions/{session_id}/voice",
    }
    timeout = root.settings.db_lock_timeout_seconds if guarded else None
    with root.transaction(
        lock_timeout_seconds=timeout, inference_deadline=inference_deadline if guarded else None
    ) as state:
        yield state
