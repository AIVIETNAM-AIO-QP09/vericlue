"""Consent/withdrawal use independent transactions, never SessionStore.save_all after key erasure."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text

from vericlue_api.core.security import _verify_token, bearer_scheme, session_token
from vericlue_api.core.session_ingress import SessionAPIRoute
from vericlue_api.schemas.privacy import (
    PrivacyConsentRequest,
    PrivacyState,
    PrivacyWithdrawalRequest,
)
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.privacy_consent import PrivacyService, erase_committed_session_files


def preflight_privacy(request: Request, session_id: str) -> None:
    root = request.app.state.vericlue
    token = session_token(request)
    _verify_token(root.settings, session_id, token)
    with root.database.sessions() as db:
        PrivacyService(root.settings, db).authorize(session_id, token)


class PrivacyAPIRoute(SessionAPIRoute):
    json_body_max_bytes = 8 * 1024

    def authenticate(self, request: Request, session_id: str) -> None:
        preflight_privacy(request, session_id)


router = APIRouter(
    prefix="/v1/sessions",
    tags=["privacy"],
    route_class=PrivacyAPIRoute,
    dependencies=[Depends(bearer_scheme)],
    responses={code: {"model": ErrorResponse} for code in (400, 401, 409, 410, 413, 503)},
)


@contextmanager
def privacy_transaction(request: Request, session_id: str) -> Iterator[tuple[PrivacyService, str]]:
    root = request.app.state.vericlue
    token = session_token(request)
    _verify_token(root.settings, session_id, token)
    with root.database.sessions.begin() as db:
        if db.bind.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        service = PrivacyService(root.settings, db)
        service.lock(session_id)
        service.authorize(session_id, token)
        yield service, token


@router.get("/{session_id}/privacy", response_model=PrivacyState)
def get_privacy(session_id: str, request: Request, response: Response) -> PrivacyState:
    response.headers["Cache-Control"] = "no-store"
    with privacy_transaction(request, session_id) as (service, _):
        result = service.state(session_id)
    return result


@router.post("/{session_id}/privacy/consent", response_model=PrivacyState)
def grant_consent(
    session_id: str, request: Request, body: PrivacyConsentRequest, response: Response
) -> PrivacyState:
    response.headers["Cache-Control"] = "no-store"
    with privacy_transaction(request, session_id) as (service, token):
        result = service.grant(session_id, token, body)
    return result


@router.post("/{session_id}/privacy/withdraw", response_model=PrivacyState)
def withdraw_consent(
    session_id: str, request: Request, body: PrivacyWithdrawalRequest, response: Response
) -> PrivacyState:
    response.headers["Cache-Control"] = "no-store"
    with privacy_transaction(request, session_id) as (service, token):
        service.withdraw(session_id, token)
    # The response is sent only after the authoritative withdrawal transaction commits.
    erase_committed_session_files(request.app.state.vericlue, session_id)
    with privacy_transaction(request, session_id) as (service, _):
        result = service.state(session_id)
    return result
