"""Xác thực token HMAC đúng phiên, đúng hạn và khớp bản băm đã lưu."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vericlue_api.core.errors import ApiError
from vericlue_api.core.session_tokens import token_digest
from vericlue_api.core.state import AppState, get_state
from vericlue_api.db.models import aware
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
    state: AppState = Depends(get_state, scope="function"),
) -> Session:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    token = credentials.credentials
    if not state.settings.session_token_signer.verify(token, session_id):
        raise _unauthorized()
    session = state.sessions.get(session_id)
    # Phiên không tồn tại cũng trả 401 để không lộ phiên nào có thật.
    if (
        session is None
        or aware(session.token_expires_at) <= datetime.now(UTC)
        or not secrets.compare_digest(session.token_hash, token_digest(token))
    ):
        raise _unauthorized()
    return session
