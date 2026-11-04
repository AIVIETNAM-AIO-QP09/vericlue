"""Dashboard access routes; session bearers and account-access bearers are distinct."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from starlette.responses import JSONResponse

from vericlue_api.core.security import bearer_scheme, require_session, session_token
from vericlue_api.core.session_ingress import SessionAPIRoute
from vericlue_api.core.state import AppState, get_state
from vericlue_api.schemas.account_access import (
    AccountAccessSession,
    AccountAccessSetupRequest,
    AccountLogoutResponse,
    AccountPasswordRequest,
    AccountProfile,
)
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.account_access import AccountAccess, LoginRejected
from vericlue_api.services.session_store import Session

ERRORS = {code: {"model": ErrorResponse} for code in (401, 409, 410, 429, 503)}
router = APIRouter(prefix="/v1/account-access", tags=["account-access"])
session_router = APIRouter(
    prefix="/v1/sessions", tags=["account-access"], route_class=SessionAPIRoute
)
StateDep = Annotated[AppState, Depends(get_state, scope="function")]
SessionDep = Annotated[Session, Depends(require_session)]


@session_router.post(
    "/{session_id}/account-access/setup", response_model=AccountProfile, responses=ERRORS
)
def setup_account_access(
    session: SessionDep, state: StateDep, body: AccountAccessSetupRequest, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    return AccountAccess(state).setup(session, body)


@session_router.post(
    "/{session_id}/account-access/face", response_model=AccountAccessSession, responses=ERRORS
)
def exchange_account_face(session: SessionDep, state: StateDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return AccountAccess(state).face(session)


@router.post("/password", response_model=AccountAccessSession, responses=ERRORS)
def password_login(
    state: StateDep, body: AccountPasswordRequest, request: Request, response: Response
):
    response.headers["Cache-Control"] = "no-store"
    result = AccountAccess(state).password(body, request.client.host if request.client else "")
    if isinstance(result, LoginRejected):
        headers = {"Cache-Control": "no-store"}
        if result.error.status_code == 429:
            headers["Retry-After"] = "300"
        return JSONResponse(
            {"error_code": result.error.error_code, "message": result.error.message},
            status_code=result.error.status_code,
            headers=headers,
        )
    return result


@router.get(
    "/me", response_model=AccountProfile, responses=ERRORS, dependencies=[Depends(bearer_scheme)]
)
def account_profile(state: StateDep, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return AccountAccess(state).current(session_token(request))[1]


@router.post(
    "/logout",
    response_model=AccountLogoutResponse,
    responses=ERRORS,
    dependencies=[Depends(bearer_scheme)],
)
def account_logout(state: StateDep, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    AccountAccess(state).logout(session_token(request))
    return AccountLogoutResponse()
