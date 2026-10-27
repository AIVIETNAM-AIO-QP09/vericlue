"""Server-to-server credential verification, separate from citizen/staff authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from vericlue_api.core.credential_access import verifier_bearer
from vericlue_api.core.credential_state import get_credential_db
from vericlue_api.schemas.credential import (
    CredentialChallengeRequest,
    VerificationAccepted,
    VerificationChallenge,
    VerificationPresentation,
    VerificationRejected,
)
from vericlue_api.schemas.session import ErrorResponse
from vericlue_api.services.credential_verifier import CredentialVerifier

router = APIRouter(
    prefix="/v1/credentials",
    tags=["credentials"],
    dependencies=[Depends(verifier_bearer)],
    responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
DatabaseDep = Annotated[Session, Depends(get_credential_db, scope="function")]


def _service(request: Request, db: Session) -> CredentialVerifier:
    return CredentialVerifier(
        request.app.state.vericlue.settings, db, request.state.credential_audience
    )


@router.post("/challenges", response_model=VerificationChallenge)
def challenge(
    body: CredentialChallengeRequest, request: Request, db: DatabaseDep, response: Response
) -> VerificationChallenge:
    response.headers["Cache-Control"] = "no-store"
    return _service(request, db).challenge()


@router.post("/verify", response_model=VerificationAccepted | VerificationRejected)
def verify(
    body: VerificationPresentation, request: Request, db: DatabaseDep, response: Response
) -> VerificationAccepted | VerificationRejected:
    response.headers["Cache-Control"] = "no-store"
    return _service(request, db).verify(body)
