"""Xác thực token HMAC đúng phiên, đúng hạn và khớp bản băm đã lưu."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.session_tokens import token_digest
from vericlue_api.core.state import AppState, get_state
from vericlue_api.db.models import aware
from vericlue_api.services.privacy_consent import require_categories, require_session_active
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import Session, SessionStore

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token theo phiên, nhận từ POST /v1/sessions (ADR-0011). Sai hoặc thiếu → 401.",
)


def _unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", "Thiếu hoặc sai token phiên.")


def session_token(request: Request) -> str:
    """Read one bearer header; never let proxies and the application choose different tokens."""
    values = request.headers.getlist("Authorization")
    if len(values) != 1:
        raise _unauthorized()
    scheme, _, token = values[0].partition(" ")
    if scheme.lower() != "bearer" or not token or token != token.strip():
        raise _unauthorized()
    return token


def _verify_token(settings: Settings, session_id: str, token: str) -> None:
    if not settings.session_token_signer.verify(token, session_id):
        raise _unauthorized()


def _current_session(sessions: SessionStore, session_id: str, token: str) -> Session:
    require_session_active(sessions.db, session_id)
    session = sessions.get(session_id)
    # Missing, expired and superseded credentials have the same response.
    if (
        session is None
        or aware(session.token_expires_at) <= datetime.now(UTC)
        or not secrets.compare_digest(session.token_hash, token_digest(token))
    ):
        raise _unauthorized()
    require_session_active(sessions.db, session_id)
    return session


def preflight_session(request: Request, session_id: str) -> None:
    """Authenticate before reading a body, releasing DB/key locks before waiting for upload.

    This intentionally does not use ApplicationState.transaction/save_all: a read
    must not refresh activity, revive deleted media or overwrite another request.
    The ordinary dependency validates again after body parsing.
    """
    root = request.app.state.vericlue
    token = session_token(request)
    _verify_token(root.settings, session_id, token)
    with root.database.sessions() as db:
        store = SessionStore(db, privacy=SessionPrivacy(root.settings, db))
        session = _current_session(store, session_id, token)
        require_categories(
            db, root.settings, session, getattr(request.scope.get("endpoint"), "__name__", "")
        )


def require_session(
    session_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    state: AppState = Depends(get_state, scope="function"),
) -> Session:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    token = session_token(request)
    _verify_token(state.settings, session_id, token)
    session = _current_session(state.sessions, session_id, token)
    require_categories(
        state.db, state.settings, session, getattr(request.scope.get("endpoint"), "__name__", "")
    )
    return session
