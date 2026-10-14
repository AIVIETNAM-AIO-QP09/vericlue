"""Xác thực phiên bằng `Authorization: Bearer`.

TẠM — PLAT-06 thay bằng token HMAC gắn session_id, hết hạn ~5 phút, kèm máy trạng thái
chống phát lại (mỗi bước một lần mỗi lượt, lần hai → 409). Hiện chỉ kiểm: có header Bearer
và khớp token của phiên, nếu không → 401.
"""

from __future__ import annotations

import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vericlue_api.core.errors import ApiError
from vericlue_api.core.state import AppState, get_state
from vericlue_api.services.session_store import Session

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token theo phiên, nhận từ POST /v1/sessions (ADR-0011). Sai hoặc thiếu → 401.",
)


def _unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")


def require_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    state: AppState = Depends(get_state),
) -> Session:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    session = state.sessions.get(session_id)
    # Phiên không tồn tại cũng trả 401 để không lộ phiên nào có thật.
    if session is None or not secrets.compare_digest(session.token, credentials.credentials):
        raise _unauthorized()
    return session
