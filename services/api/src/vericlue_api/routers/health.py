"""GET /healthz — kiểm tra máy chủ còn sống và đang dùng mô hình gì."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from vericlue_api import __version__
from vericlue_api.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    version: str
    mock_models: bool
    failed_modules: list[str]


@router.get("/healthz", response_model=Health)
def healthz(request: Request, settings: Settings = Depends(get_settings)) -> Health:
    failed = request.app.state.vericlue.orchestrator.failed_modules
    return Health(
        status="degraded" if failed else "ok",
        version=__version__,
        mock_models=bool(settings.use_mock_models),  # mixed vẫn có module mock → true
        failed_modules=failed,
    )
