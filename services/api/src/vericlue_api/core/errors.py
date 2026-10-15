"""Lỗi theo một định dạng duy nhất: `{error_code, message}` (khớp `ErrorResponse` trong hợp đồng)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


def _json(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error_code": error_code, "message": message}
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SQLAlchemyError)
    async def _storage_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Never return SQL, connection URLs, tokens or driver parameters to callers.
        return _json(
            503, "storage_unavailable", "Không thể truy cập kho dữ liệu. Vui lòng thử lại."
        )

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _json(exc.status_code, exc.error_code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _json(exc.status_code, f"http_{exc.status_code}", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = ", ".join(
            ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]) for e in exc.errors()
        )
        return _json(422, "validation_error", f"Dữ liệu không hợp lệ: {fields}")
