"""Strict verifier child-output boundary, with native crypto covered by API tests."""

import json

import pytest
from fastapi.testclient import TestClient
from test_credential_verifier import A, challenge, presentation
from test_credential_verifier import verifier_env as verifier_env

from vericlue_api.core.errors import ApiError
from vericlue_api.main import create_app
from vericlue_api.schemas.credential import VerificationChallenge, VerificationPresentation
from vericlue_api.services.credential_verifier_worker import CredentialProofWorker


@pytest.mark.parametrize(
    "fault", ["accept", "reject", "integer", "claim", "extra", "missing", "malformed"]
)
def test_public_only_worker_context_and_strict_response(verifier_env, monkeypatch, fault):
    with TestClient(create_app()) as client:
        q = challenge(client, verifier_env["a"])
        body = presentation(q)
        result = {
            "valid": True,
            "assurance": "server-decision",
            "disclosed": body["disclosed"].copy(),
            "pseudonym": body["pseudonym"],
        }
        if fault == "reject":
            result = {"valid": False}
        elif fault == "integer":
            result["disclosed"]["verification_completed"] = 1
        elif fault == "claim":
            result["disclosed"]["issuer"] = "wrong-issuer"
        elif fault == "extra":
            result["account_id"] = "hidden-id-must-not-return"
        elif fault == "missing":
            result.pop("assurance")

        def child(settings, argv, packet):
            assert len(argv) == 2 and argv[1].endswith("verifier-worker.mjs")
            data = json.loads(packet)
            assert set(data) == {"public_key", "issuer", "audience", "challenge", "presentation"}
            assert data["audience"] == A and data["challenge"] == q
            assert data["presentation"] == body
            assert b"secret_key" not in packet and b"holderSecret" not in packet
            return b"invalid-json" if fault == "malformed" else json.dumps(result).encode()

        monkeypatch.setattr("vericlue_api.services.credential_verifier_worker.run_packet", child)
        worker = CredentialProofWorker(client.app.state.vericlue.settings)
        args = (
            VerificationChallenge.model_validate(q),
            VerificationPresentation.model_validate(body),
        )
        if fault in {"accept", "reject"}:
            assert worker.verify(*args) is (fault == "accept")
        else:
            with pytest.raises(ApiError) as error:
                worker.verify(*args)
            assert error.value.status_code == 503
