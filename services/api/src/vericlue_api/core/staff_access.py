"""Demo staff authentication before body parsing, independent of privacy/model mode."""

import json
import re
import secrets

from fastapi.security import HTTPBearer
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import Scope

from vericlue_api.core.config import Settings

staff_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="StaffBearer",
    description="Credential nhân viên bắt buộc cho bàn duyệt/giám định; không dùng token người dân.",
)

TOKEN = re.compile(r"[A-Za-z0-9._~+/-]+={0,}", re.ASCII)


def is_staff_path(scope: Scope) -> bool:
    """Match decoded application routes, including deployments with a root path."""
    path = scope["path"]
    root = scope.get("root_path", "")
    if root and (path == root or path.startswith(root + "/")):
        path = path[len(root) :]
    return any(
        path == base or path.startswith(base + "/") for base in ("/v1/review", "/v1/forensic")
    )


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate credential")
        result[key] = value
    return result


def _credentials(settings: Settings) -> dict[str, str]:
    if settings.staff_access_tokens is None:
        raise ValueError("Staff credentials required")
    raw = settings.staff_access_tokens.get_secret_value()
    if len(raw) > 65536:
        raise ValueError("Staff credentials too large")
    tokens = json.loads(raw, object_pairs_hook=_unique_pairs)
    if (
        not isinstance(tokens, dict)
        or not 1 <= len(tokens) <= 256
        or not all(
            isinstance(token, str)
            and 32 <= len(token) <= 512
            and TOKEN.fullmatch(token) is not None
            and isinstance(actor, str)
            and 1 <= len(actor) <= 100
            and actor.strip()
            and actor.isprintable()
            and actor != "staff-unverified"
            for token, actor in tokens.items()
        )
    ):
        raise ValueError("Invalid staff credentials")
    return tokens


def _reject(status: int) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        {
            "error_code": "unauthorized" if status == 401 else "staff_unavailable",
            "message": (
                "Thiếu hoặc sai quyền truy cập."
                if status == 401
                else "Chức năng nhân viên chưa sẵn sàng."
            ),
        },
        status_code=status,
        headers=headers,
    )


def authenticate_staff(request: Request, settings: Settings) -> JSONResponse | None:
    """Authenticate staff before any upload, DB access or model work; never log tokens."""
    if request.method == "OPTIONS" or not is_staff_path(request.scope):
        return None
    try:
        tokens = _credentials(settings)
    except (TypeError, ValueError, RecursionError):
        return _reject(503)
    auth_values = request.headers.getlist("Authorization")
    if len(auth_values) != 1:
        return _reject(401)
    auth = auth_values[0]
    scheme, _, supplied = auth.partition(" ")
    actor = None
    if scheme.lower() == "bearer" and 32 <= len(supplied) <= 512 and TOKEN.fullmatch(supplied):
        for token, name in tokens.items():
            if secrets.compare_digest(token.encode("ascii"), supplied.encode("ascii")):
                actor = name
    if actor is None:
        return _reject(401)
    request.state.staff_actor = actor
    return None
