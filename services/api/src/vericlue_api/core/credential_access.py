"""Dedicated integration credentials bind each verifier to a server-configured origin."""

import json
import secrets

from fastapi.security import HTTPBearer
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import Scope

from vericlue_api.core.config import Settings
from vericlue_api.core.staff_access import TOKEN, _unique_pairs
from vericlue_api.schemas.credential import https_origin

verifier_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="CredentialVerifierBearer",
    description="Credential tích hợp server-to-server; audience lấy từ cấu hình, không từ client.",
)


def is_verifier_path(scope: Scope) -> bool:
    path, root = scope["path"], scope.get("root_path", "")
    if root and (path == root or path.startswith(root + "/")):
        path = path[len(root) :]
    return path == "/v1/credentials" or path.startswith("/v1/credentials/")


def authenticate_verifier(request: Request, settings: Settings) -> JSONResponse | None:
    """Reject before body parsing, DB connections or crypto; never trust caller origins."""
    if request.method == "OPTIONS" or not is_verifier_path(request.scope):
        return None
    status = 503
    try:
        if not settings.credential_verifier or settings.credential_verifier_tokens is None:
            raise ValueError("Not configured")
        raw = settings.credential_verifier_tokens.get_secret_value()
        if len(raw) > 65536:
            raise ValueError("Invalid configuration")
        tokens = json.loads(raw, object_pairs_hook=_unique_pairs)
        if not isinstance(tokens, dict) or not 1 <= len(tokens) <= 256:
            raise ValueError("Invalid configuration")
        for token, audience in tokens.items():
            if (
                not isinstance(token, str)
                or not 32 <= len(token) <= 512
                or not TOKEN.fullmatch(token)
                or not isinstance(audience, str)
            ):
                raise ValueError("Invalid configuration")
            https_origin(audience)
        status = 401
        supplied = request.headers.getlist("Authorization")
        if len(supplied) == 1:
            scheme, _, value = supplied[0].partition(" ")
            if scheme.lower() == "bearer" and 32 <= len(value) <= 512 and TOKEN.fullmatch(value):
                for token, audience in tokens.items():
                    if secrets.compare_digest(token.encode("ascii"), value.encode("ascii")):
                        request.state.credential_audience = audience
                        return None
    except (ValueError, TypeError, RecursionError):
        status = 503
    headers = {"Cache-Control": "no-store"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        {
            "error_code": "unauthorized" if status == 401 else "credential_verifier_unavailable",
            "message": "Thiếu hoặc sai quyền truy cập."
            if status == 401
            else "Chức năng kiểm tra chứng nhận chưa sẵn sàng.",
        },
        status_code=status,
        headers=headers,
    )
