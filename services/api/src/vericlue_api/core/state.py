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
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.enrollment import EnrollmentService
from vericlue_api.services.forensic_service import ForensicStore
from vericlue_api.services.identity_steps import IdentitySteps
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_flow import SessionFlow
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import SessionStore
from vericlue_api.services.signed_results import SignedResultService


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
    identity: IdentitySteps = field(init=False)
    privacy: SessionPrivacy = field(init=False)
    accounts: AccountStore = field(init=False)
    enrollment: EnrollmentService = field(init=False)
    signed_results: SignedResultService = field(init=False)

    def __post_init__(self) -> None:
        self.privacy = SessionPrivacy(self.settings, self.db)
        self.accounts = AccountStore(self.settings, self.db)
        self.signed_results = SignedResultService(self.settings, self.db, self.accounts)
        self.enrollment = EnrollmentService(
            self.accounts,
            self.privacy,
            self.orchestrator.extract_template,
            deadline=self.inference_deadline,
        )
        base_runner = partial(self.orchestrator.run, deadline=self.inference_deadline)

        def runner(modules, *, session_id, **kwargs):
            prepared, lease = self.privacy.prepare(session_id, kwargs)
            try:
                return base_runner(modules, session_id=session_id, **prepared, media_lease=lease)
            finally:
                if lease is not None:
                    lease.release()

        self.sessions = SessionStore(self.db, privacy=self.privacy)
        self.reviews = ReviewStore(self.db, runner=runner, privacy=self.privacy)
        self.forensic = ForensicStore(
            self.settings.router_config.face.b,
            self.settings.router_config.face.a,
            self.db,
            self.settings.media_dir,
            runner=runner,
            # true → bản mock; false/mixed → phân tích thật
            mock=self.settings.use_mock_models is True,
            report_signer=lambda: self.settings.report_signer,
        )
        self.flow = SessionFlow(
            self.settings,
            self.sessions,
            self.reviews,
            runner=runner,
            router=self.orchestrator.router,
            privacy=self.privacy,
            enroll=self.enrollment.complete,
            accounts=self.accounts,
        )
        self.identity = IdentitySteps(self.settings, privacy=self.privacy)


class ApplicationState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        _ = settings.router_config  # Freeze the raw-file snapshot once for this application.
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
                if self.settings.use_mock_models is not True:
                    state.forensic.fail_interrupted()  # job giám định dở dang của lần chạy trước
            self._initialized = True


def get_state(request: Request) -> Iterator[AppState]:
    # Leave 200 ms for policy/flush/commit/serialization under a healthy DB.
    root = request.app.state.vericlue
    budget = (
        root.settings.session_model_timeout_seconds + 0.8
        if root.settings.session_face_models
        or root.settings.session_voice_models
        or root.settings.identity_voice_continuity
        else root.settings.inference_budget_seconds
    )
    inference_deadline = perf_counter() + budget
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
        state.reviews.actor = getattr(request.state, "staff_actor", "staff-unverified")
        yield state
