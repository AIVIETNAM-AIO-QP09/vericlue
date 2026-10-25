"""Optional demo staff authentication; credentials are separate from citizen sessions."""

import json
import secrets

from fastapi.security import HTTPBearer
from starlette.requests import Request
from starlette.responses import JSONResponse

from vericlue_api.core.config import Settings

staff_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="StaffBearer",
    description="Credential nhân viên cấu hình riêng khi SESSION_PRIVACY=true; không dùng token người dân.",
)


def authenticate_staff(request: Request, settings: Settings) -> JSONResponse | None:
    """Fail closed for all review routes in privacy mode, without logging credentials."""
    if (
        not settings.session_privacy
        or request.method == "OPTIONS"
        or not request.scope["path"].startswith("/v1/review/")
    ):
        return None
    try:
        tokens = json.loads(settings.staff_access_tokens.get_secret_value())
        if (
            not isinstance(tokens, dict)
            or not tokens
            or not all(
                isinstance(k, str)
                and len(k.encode()) >= 32
                and isinstance(v, str)
                and 1 <= len(v) <= 100
                for k, v in tokens.items()
            )
        ):
            raise ValueError("Invalid credentials configuration")
    except Exception:
        return JSONResponse(
            {"error_code": "staff_unavailable", "message": "Bàn duyệt chưa sẵn sàng."},
            status_code=503,
        )
    auth = request.headers.get("Authorization", "")
    scheme, _, supplied = auth.partition(" ")
    actor = None
    if scheme.lower() == "bearer" and supplied:
        for token, name in tokens.items():
            if secrets.compare_digest(token.encode("utf-8"), supplied.encode("utf-8")):
                actor = name
    if actor is None:
        return JSONResponse(
            {"error_code": "unauthorized", "message": "Thiếu hoặc sai quyền truy cập."},
            status_code=401,
        )
    request.state.staff_actor = actor
    return None
