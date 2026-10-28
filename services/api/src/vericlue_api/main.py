"""Điểm vào của API.

Chạy:  uv run uvicorn vericlue_api.main:app --reload --app-dir services/api/src
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from vericlue_api import __version__
from vericlue_api.core.config import get_settings
from vericlue_api.core.credential_access import authenticate_verifier
from vericlue_api.core.errors import install_error_handlers
from vericlue_api.core.request_limits import RequestLimitsMiddleware
from vericlue_api.core.security_profile import validate_security_profile
from vericlue_api.core.staff_access import authenticate_staff, is_staff_path
from vericlue_api.core.state import ApplicationState
from vericlue_api.routers import credentials, forensic, health, privacy, review, sessions
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
    validate_security_profile(settings)
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(RequestLimitsMiddleware, settings=settings)
    install_error_handlers(app)
    app.state.vericlue = ApplicationState(settings=settings)

    @app.middleware("http")
    async def staff_access(request, call_next):
        if settings.product_mode == "ekyc" and is_staff_path(request.scope):
            return JSONResponse(
                {"error_code": "http_404", "message": "Không tìm thấy chức năng này."},
                status_code=404,
                headers={"Cache-Control": "no-store"},
            )
        rejected = authenticate_staff(request, settings)
        if rejected is None:
            rejected = authenticate_verifier(request, settings)
        response = rejected if rejected is not None else await call_next(request)
        # Session/consent errors can contain state as well as successful responses.
        response.headers["Cache-Control"] = "no-store"
        return response

    # CORS must wrap auth rejections as well as successful staff responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-VeriClue-Signature",
            "X-VeriClue-Report-SHA256",
            "Retry-After",
            "WWW-Authenticate",
            "X-VeriClue-Key-Id",
            "X-VeriClue-Signature-Algorithm",
        ],
    )

    routers = [
        health.router,
        sessions.router,
        sessions.keys_router,
        privacy.router,
        credentials.router,
    ]
    if settings.product_mode == "tools":
        routers.extend((review.router, forensic.router))
    for router in routers:
        app.include_router(router)
    return app


app = create_app()
