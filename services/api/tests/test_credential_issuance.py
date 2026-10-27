"""Real device/result crypto and DB with synthetic server decisions; worker boundary is explicit."""

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from contract_utils import validate
from test_account_auth import new_key, recovery_ready, seeded, signed
from test_accounts import private_client as private_client
from test_signed_result_api import configure, ready

from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import encode
from vericlue_api.db.models import (
    CredentialIssuanceRow,
    DecisionRow,
    SessionRow,
    utcnow,
)
from vericlue_api.schemas.credential import CredentialIssueRequest, VerificationCredential
from vericlue_api.services.credential_issuance import CredentialIssuance
from vericlue_api.services.credential_worker import CredentialWorker
from vericlue_ml.common.result import Module, Status

REAL_ISSUE = CredentialWorker.issue


def setup_credential(client, tmp_path, monkeypatch):
    key, receipt, _, _ = seeded(client)
    configure(client, tmp_path)
    body, headers = ready(client, receipt, key)
    path = tmp_path / "bbs-keys.json"
    # Worker-boundary tests use shape-only random bytes, never claim fake BBS signatures verify.
    public = secrets.token_bytes(96)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "secret_key": encode(secrets.token_bytes(32)),
                "public_key": encode(public),
            }
        ),
        encoding="utf-8",
    )
    root = client.app.state.vericlue
    root.settings = root.settings.model_copy(
        update={
            "private_credentials": True,
            "credential_node": sys.executable,
            "credential_worker_file": str(tmp_path / "issuer-worker.mjs"),
            "credential_signing_key_file": str(path),
        }
    )
    (tmp_path / "issuer-worker.mjs").write_text("// synthetic worker boundary", encoding="utf-8")
    calls = []

    def worker(self, commitment, claims):
        calls.append(commitment)
        return VerificationCredential(
            claims=claims,
            signature=encode(secrets.token_bytes(80)),
            signer_entropy="1" * 64,
            key_id=hashlib.sha256(public).hexdigest(),
        )

    monkeypatch.setattr(CredentialWorker, "issue", worker)
    return key, receipt, body, headers, calls


def offer():
    return {"commitment": encode(secrets.token_bytes(176)), "consent": True}


def authorize(client, body, headers, request, key):
    response = client.post(
        f"/v1/sessions/{body['session_id']}/credential-authorization", headers=headers, json=request
    )
    assert response.status_code == 200, response.text
    validate(response.json(), "credential", "CredentialAuthorization")
    signature = signed(key, base64.b64decode(response.json()["message"]))
    return {**request, "device_signature": signature}


def test_issue_is_device_bound_encrypted_and_idempotent(private_client, tmp_path, monkeypatch):
    key, receipt, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    request = authorize(private_client, body, headers, offer(), key)
    path = f"/v1/sessions/{body['session_id']}/credential"
    first = private_client.post(path, headers=headers, json=request)
    assert first.status_code == 200, first.text
    validate(first.json(), "credential", "VerificationCredential")
    assert first.headers["Cache-Control"] == "no-store"
    assert first.json()["claims"]["account_id"] == receipt.account_id
    assert first.json()["claims"]["assurance"] == "server-decision"
    assert "age_over_18" not in first.text
    assert private_client.post(path, headers=headers, json=request).json() == first.json()
    assert len(calls) == 1
    root = private_client.app.state.vericlue
    with root.database.sessions() as db:
        row = db.get(CredentialIssuanceRow, body["session_id"])
        assert set(row.payload) == {"encrypted_session_v1"}
        assert receipt.account_id not in json.dumps(row.payload)
        assert first.json()["signature"] not in json.dumps(row.payload)


@pytest.mark.parametrize("fault", ["unsigned", "foreign_key", "other_offer", "other_session"])
def test_stolen_bearer_is_insufficient(private_client, tmp_path, monkeypatch, fault):
    key, receipt, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    request = authorize(private_client, body, headers, offer(), key)
    if fault == "unsigned":
        request["device_signature"] = base64.b64encode(b"invalid-signature").decode()
    elif fault == "foreign_key":
        request = authorize(private_client, body, headers, offer(), new_key())
    elif fault == "other_offer":
        request["commitment"] = offer()["commitment"]
    else:
        other_body, other_headers = ready(private_client, receipt, key)
        request = authorize(private_client, other_body, other_headers, offer(), key)
    response = private_client.post(
        f"/v1/sessions/{body['session_id']}/credential", headers=headers, json=request
    )
    assert response.status_code == 409
    assert calls == []


@pytest.mark.parametrize(
    "fault",
    [
        "mock",
        "mixed",
        "review",
        "incomplete",
        "degraded",
        "missing_match",
        "deleted",
        "expired",
        "deny",
        "old_device",
    ],
)
def test_ineligible_session_cannot_get_authorization(private_client, tmp_path, monkeypatch, fault):
    _, receipt, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    root = private_client.app.state.vericlue
    if fault == "mixed":
        root.settings = root.settings.model_copy(update={"use_mock_models": "mixed"})
    with root.transaction() as state:
        session = state.sessions.get(body["session_id"])
        row = state.db.get(SessionRow, session.session_id)
        if fault == "mock":
            session.created_model_mode = "mock"
        elif fault == "review":
            row.ever_review = True
        elif fault == "incomplete":
            session.completed = False
        elif fault == "degraded":
            session.results[Module.FACE_PAD].status = Status.DEGRADED
        elif fault == "missing_match":
            session.results.pop(Module.FACE_MATCH)
        elif fault == "deleted":
            row.media_deleted_at = utcnow()
        elif fault == "expired":
            from sqlalchemy import select

            decision = state.db.scalar(
                select(DecisionRow).where(DecisionRow.session_id == session.session_id)
            )
            decision.created_at = utcnow() - timedelta(minutes=2)
        elif fault == "deny":
            state.sessions.record_decision(
                session, "deny", thresholds={}, config_version="synthetic-deny"
            )
        elif fault == "old_device":
            state.flow.settings = state.settings.model_copy(update={"use_mock_models": True})
            recovery = recovery_ready(state, receipt, new_key())
            recovery.created_model_mode = "real"  # Trusted historical decision fixture only.
            state.flow.settings = state.settings
            state.accounts.recover(recovery)
    if fault == "deleted":
        # Simulate cleanup without loading SessionStore, which refreshes its live snapshot.
        with root.database.sessions.begin() as db:
            db.get(SessionRow, body["session_id"]).media_deleted_at = utcnow()
    response = private_client.post(
        f"/v1/sessions/{body['session_id']}/credential-authorization", headers=headers, json=offer()
    )
    assert response.status_code in {409, 410}
    assert calls == []


def test_different_holder_cannot_reissue_same_session(private_client, tmp_path, monkeypatch):
    key, _, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    path = f"/v1/sessions/{body['session_id']}/credential"
    first = authorize(private_client, body, headers, offer(), key)
    assert private_client.post(path, headers=headers, json=first).status_code == 200
    other = authorize(private_client, body, headers, offer(), key)
    assert private_client.post(path, headers=headers, json=other).status_code == 409
    assert len(calls) == 1


def test_sqlite_parallel_retry_returns_one_identical_credential(
    private_client, tmp_path, monkeypatch
):
    key, _, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    request = authorize(private_client, body, headers, offer(), key)
    ready = Barrier(2)

    def send(_):
        ready.wait(timeout=10)
        return private_client.post(
            f"/v1/sessions/{body['session_id']}/credential", headers=headers, json=request
        )

    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(send, range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert len(calls) == 1


def test_worker_failure_and_outer_rollback_leave_no_issuance(private_client, tmp_path, monkeypatch):
    key, _, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    request = authorize(private_client, body, headers, offer(), key)
    root = private_client.app.state.vericlue
    with pytest.raises(RuntimeError), root.transaction() as state:
        CredentialIssuance(state).issue(
            state.sessions.get(body["session_id"]), CredentialIssueRequest.model_validate(request)
        )
        raise RuntimeError("synthetic failed request after issuance")
    with root.database.sessions() as db:
        assert db.get(CredentialIssuanceRow, body["session_id"]) is None
    assert (
        private_client.post(
            f"/v1/sessions/{body['session_id']}/credential", headers=headers, json=request
        ).status_code
        == 200
    )
    assert len(calls) == 2


def test_worker_error_does_not_consume_session_and_can_retry(private_client, tmp_path, monkeypatch):
    key, _, body, headers, _ = setup_credential(private_client, tmp_path, monkeypatch)
    request = authorize(private_client, body, headers, offer(), key)
    original = CredentialWorker.issue

    def fail(*args):
        raise ApiError(503, "credential_unavailable", "Chưa thể cấp chứng nhận.")

    monkeypatch.setattr(CredentialWorker, "issue", fail)
    path = f"/v1/sessions/{body['session_id']}/credential"
    assert private_client.post(path, headers=headers, json=request).status_code == 503
    with private_client.app.state.vericlue.database.sessions() as db:
        assert db.get(CredentialIssuanceRow, body["session_id"]) is None
    monkeypatch.setattr(CredentialWorker, "issue", original)
    assert private_client.post(path, headers=headers, json=request).status_code == 200


def test_cached_credential_is_not_returned_after_decision_changes(
    private_client, tmp_path, monkeypatch
):
    key, _, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    request = authorize(private_client, body, headers, offer(), key)
    path = f"/v1/sessions/{body['session_id']}/credential"
    assert private_client.post(path, headers=headers, json=request).status_code == 200
    root = private_client.app.state.vericlue
    with root.transaction() as state:
        state.sessions.record_decision(
            state.sessions.get(body["session_id"]),
            "deny",
            thresholds={},
            config_version="synthetic-changed",
        )
    assert private_client.post(path, headers=headers, json=request).status_code == 409
    assert len(calls) == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"consent": False},
        {"consent": 1},
        {"status": "pass"},
        {"age_over_18": True},
        {"commitment": "A" * 234 + "B"},
    ],
)
def test_client_cannot_supply_claims_or_implicit_consent(
    private_client, tmp_path, monkeypatch, patch
):
    _, _, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    response = private_client.post(
        f"/v1/sessions/{body['session_id']}/credential-authorization",
        headers=headers,
        json={**offer(), **patch},
    )
    assert response.status_code == 422
    assert calls == []


def test_no_or_wrong_session_token_is_rejected(private_client, tmp_path, monkeypatch):
    _, _, body, _, calls = setup_credential(private_client, tmp_path, monkeypatch)
    path = f"/v1/sessions/{body['session_id']}/credential-authorization"
    assert private_client.post(path, json=offer()).status_code == 401
    assert (
        private_client.post(
            path, headers={"Authorization": "Bearer invalid"}, json=offer()
        ).status_code
        == 401
    )
    assert calls == []


def test_public_key_does_not_initialize_models_or_database(private_client, tmp_path, monkeypatch):
    setup_credential(private_client, tmp_path, monkeypatch)
    root = private_client.app.state.vericlue
    monkeypatch.setattr(
        root, "initialize", lambda: pytest.fail("public key must not initialize models")
    )
    monkeypatch.setattr(root, "transaction", lambda: pytest.fail("public key must not read DB"))
    response = private_client.get("/v1/credential-signing-key")
    assert response.status_code == 200
    validate(response.json(), "credential", "CredentialKey")
    assert "secret" not in response.text


def test_missing_configuration_never_falls_back(private_client, tmp_path, monkeypatch):
    _, _, body, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    root = private_client.app.state.vericlue
    root.settings = root.settings.model_copy(update={"private_credentials": False})
    assert private_client.get("/v1/credential-signing-key").status_code == 503
    assert (
        private_client.post(
            f"/v1/sessions/{body['session_id']}/credential-authorization",
            headers=headers,
            json=offer(),
        ).status_code
        == 503
    )
    assert calls == []


@pytest.mark.skipif(
    not os.environ.get("TEST_CREDENTIAL_NODE"), reason="opt-in native Node BBS runtime"
)
@pytest.mark.parametrize("purpose", ["reauth", "recovery"])
def test_native_http_issue_and_holder_proof(private_client, tmp_path, purpose):
    node = os.environ["TEST_CREDENTIAL_NODE"]
    root_path = Path(__file__).resolve().parents[3]
    package = root_path / "services/credentials"
    key_file = tmp_path / "native-bbs.json"
    subprocess.run(
        [node, str(package / "keygen.mjs"), "--out", str(key_file)],
        check=True,
        capture_output=True,
        timeout=20,
    )
    key, receipt, _, _ = seeded(private_client)
    configure(private_client, tmp_path)
    body, headers = ready(private_client, receipt, key)
    root = private_client.app.state.vericlue
    if purpose == "recovery":
        key = new_key()
        with root.transaction() as state:
            state.flow.settings = state.settings.model_copy(update={"use_mock_models": True})
            recovery = recovery_ready(state, receipt, key)
            recovery.created_model_mode = "real"  # Trusted historical decision fixture only.
            state.flow.settings = state.settings
            state.accounts.recover(recovery)
            body = {"session_id": recovery.session_id}
            headers = {"Authorization": "Bearer " + recovery.token}
    root.settings = root.settings.model_copy(
        update={
            "private_credentials": True,
            "credential_node": node,
            "credential_worker_file": str(package / "issuer-worker.mjs"),
            "credential_signing_key_file": str(key_file),
            "credential_timeout_seconds": 10,
        }
    )

    def holder(packet):
        response = subprocess.run(
            [node, str(Path(__file__).with_name("credential_holder.mjs"))],
            input=json.dumps(packet).encode(),
            capture_output=True,
            check=True,
            timeout=20,
        )
        return json.loads(response.stdout)

    prepared = holder({"op": "prepare"})
    request = authorize(private_client, body, headers, {**prepared["offer"], "consent": True}, key)
    response = private_client.post(
        f"/v1/sessions/{body['session_id']}/credential", headers=headers, json=request
    )
    assert response.status_code == 200, response.text
    pinned = private_client.get("/v1/credential-signing-key").json()
    result = holder(
        {
            "op": "verify",
            "state": prepared["state"],
            "key": pinned,
            "credential": response.json(),
            "now": int(utcnow().timestamp()),
        }
    )
    assert result["valid"] is True and result["replay"] is False
    assert not {"source_result_id", "account_id", "device_id", "age_over_18"} & set(
        result["disclosed"]
    )
