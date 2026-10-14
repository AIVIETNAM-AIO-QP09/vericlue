"""Điểm vào của API.

Chạy:  uv run uvicorn vericlue_api.main:app --reload --app-dir services/api/src
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vericlue_api import __version__
from vericlue_api.core.config import get_settings
from vericlue_api.core.errors import install_error_handlers
from vericlue_api.core.state import AppState
from vericlue_api.routers import forensic, health, review, sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-VeriClue-Signature", "X-VeriClue-Report-SHA256"],
    )
    install_error_handlers(app)
    app.state.vericlue = AppState(settings=settings)
    for router in (health.router, sessions.router, review.router, forensic.router):
        app.include_router(router)
    return app


app = create_app()
