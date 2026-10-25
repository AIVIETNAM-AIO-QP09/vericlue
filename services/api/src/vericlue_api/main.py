"""Điểm vào của API.

Chạy:  uv run uvicorn vericlue_api.main:app --reload --app-dir services/api/src
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vericlue_api import __version__
from vericlue_api.core.config import get_settings
from vericlue_api.core.errors import install_error_handlers
from vericlue_api.core.staff_access import authenticate_staff
from vericlue_api.core.state import ApplicationState
from vericlue_api.routers import forensic, health, review, sessions
from vericlue_api.services.storage import cleanup_expired

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = app.state.vericlue
    stop = asyncio.Event()

    async def cleanup_loop():
        while not stop.is_set():
            try:
                await asyncio.to_thread(cleanup_expired, state.database, state.settings)
            except Exception:
                logging.getLogger(__name__).exception("media_cleanup_failed")
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    stop.wait(), timeout=state.settings.media_cleanup_interval_seconds
                )

    worker = None
    try:
        state.initialize()
        worker = asyncio.create_task(cleanup_loop())
        yield
    finally:
        stop.set()
        if worker is not None:
            await worker
        state.orchestrator.close()
        state.database.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-VeriClue-Signature", "X-VeriClue-Report-SHA256"],
    )
    install_error_handlers(app)
    app.state.vericlue = ApplicationState(settings=settings)

    @app.middleware("http")
    async def staff_access(request, call_next):
        rejected = authenticate_staff(request, settings)
        response = rejected if rejected is not None else await call_next(request)
        if settings.session_privacy and request.scope["path"].startswith("/v1/review/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    for router in (health.router, sessions.router, review.router, forensic.router):
        app.include_router(router)
    return app


app = create_app()
