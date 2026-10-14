"""GET /healthz — kiểm tra máy chủ còn sống và đang dùng mô hình gì."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vericlue_api import __version__
from vericlue_api.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    version: str
    mock_models: bool


@router.get("/healthz", response_model=Health)
def healthz(settings: Settings = Depends(get_settings)) -> Health:
    return Health(status="ok", version=__version__, mock_models=settings.use_mock_models)
