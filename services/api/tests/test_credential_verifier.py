"""Durable verifier boundaries; stub crypto is explicit, native tests opt into Node."""

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from conftest import staff_test_client
from contract_utils import validate
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from vericlue_api.core.config import get_settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import encode
from vericlue_api.db.models import CredentialChallengeRow, utcnow
from vericlue_api.main import create_app
from vericlue_api.schemas.credential import VerificationPresentation
from vericlue_api.services.credential_verifier import CredentialVerifier
from vericlue_api.services.credential_verifier_worker import CredentialProofWorker

A = "https://service-a.example"
B = "https://service-b.example"
ISSUER = "https://vericlue.example"


def write_public(path: Path) -> None:
    public = secrets.token_bytes(96)  # Shape-only key, exclusively for stub-boundary tests.
    path.write_text(
        json.dumps(
            {
                "algorithm": "BBS-BLS12-381-SHA-256-NYM",
                "public_key": encode(public),
                "key_id": hashlib.sha256(public).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def verifier_env(tmp_path, monkeypatch):
    first, second = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    public = tmp_path / "public-bbs.json"
    write_public(public)
    worker = tmp_path / "verifier-worker.mjs"
    worker.write_text("// stub boundary, not a BBS implementation", encoding="utf-8")
    for name, value in {
        "SESSION_PRIVACY": "false",
        "CREDENTIAL_VERIFIER": "true",
        "CREDENTIAL_VERIFIER_TOKENS": json.dumps({first: A, second: B}),
        "CREDENTIAL_VERIFIER_ISSUER": ISSUER,
        "CREDENTIAL_VERIFIER_PUBLIC_KEY_FILE": str(public),
        "CREDENTIAL_VERIFIER_WORKER_FILE": str(worker),
        "CREDENTIAL_NODE": sys.executable,
        "CREDENTIAL_SIGNING_KEY_FILE": "",
        "RESULT_SIGNING_KEY_FILE": "",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    return {
        "a": {"Authorization": "Bearer " + first},
        "b": {"Authorization": "Bearer " + second},
        "public": public,
    }


@pytest.fixture
def stub_worker(monkeypatch):
    calls = []

    def verify(self, challenge, presentation):
        calls.append((challenge, presentation))
        return True

    monkeypatch.setattr(CredentialProofWorker, "verify", verify)
    return calls


def challenge(client, headers):
    response = client.post("/v1/credentials/challenges", headers=headers, json={})
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    result = response.json()
    validate(result, "credential", "VerificationChallenge")
    return result


def presentation(q):
    now = int(utcnow().timestamp()) // 10 * 10
    return {
        "protocol": "vericlue-private-verification-v1",
        "challenge_id": q["id"],
        "disclosed": {
            "protocol": "vericlue-private-verification-v1",
            "issuer": ISSUER,
            "assurance": "server-decision",
            "verification_completed": True,
            "valid_from": now,
            "valid_until": now + 60,
            "policy_version": "vericlue-session-result-v1",
        },
        "proof": encode(bytes(496)),  # Never claim this stub proof is cryptographically valid.
        "pseudonym": encode(bytes(48)),
    }


def test_challenge_context_is_server_owned_and_no_models_or_issuer_key_needed(
    verifier_env, monkeypatch
):
    with TestClient(create_app()) as client:
        root = client.app.state.vericlue
        monkeypatch.setattr(
            root, "initialize", lambda: pytest.fail("verifier route must not initialize models")
        )
        a = challenge(client, verifier_env["a"])
        b = challenge(client, verifier_env["b"])
        assert a["audience"] == A and b["audience"] == B
        assert a["id"] != b["id"] and a["nonce"] != b["nonce"]
        assert a["expires_at"] - a["issued_at"] == 60
        assert root.settings.private_credentials is False
        response = client.post(
            "/v1/credentials/challenges", headers=verifier_env["a"], json={"audience": B}
        )
        assert response.status_code == 422


def test_restart_and_independent_instances_share_one_use_state(verifier_env, stub_worker):
    with TestClient(create_app()) as first:
        q = challenge(first, verifier_env["a"])
    with TestClient(create_app()) as second:
        response = second.post(
            "/v1/credentials/verify", headers=verifier_env["a"], json=presentation(q)
        )
        assert response.status_code == 200 and response.json()["valid"] is True
        validate(response.json(), "credential", "VerificationAccepted")
    with TestClient(create_app()) as restarted:
        result = restarted.post(
            "/v1/credentials/verify", headers=verifier_env["a"], json=presentation(q)
        )
        assert result.json() == {"valid": False}
        with restarted.app.state.vericlue.database.sessions() as db:
            assert db.get(CredentialChallengeRow, q["id"]) is None
    assert len(stub_worker) == 1


def test_simultaneous_sqlite_instances_accept_only_once(verifier_env, stub_worker):
    with TestClient(create_app()) as first, TestClient(create_app()) as second:
        q = challenge(first, verifier_env["a"])
        payload = presentation(q)
        barrier = Barrier(2)

        def submit(client):
            barrier.wait(timeout=10)
            return client.post("/v1/credentials/verify", headers=verifier_env["a"], json=payload)

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(submit, (first, second)))
        assert all(r.status_code == 200 for r in results)
        assert sorted(r.json()["valid"] for r in results) == [False, True]
        assert len(stub_worker) == 1


@pytest.mark.parametrize(
    "fault",
    [
        "audience",
        "issuer",
        "key",
        "challenge_expired",
        "credential_expired",
        "unknown_id",
        "encoding",
    ],
)
def test_wrong_context_is_rejected_without_crypto(verifier_env, stub_worker, fault):
    with TestClient(create_app()) as client:
        q = challenge(client, verifier_env["a"])
        body = presentation(q)
        headers = verifier_env["a"]
        if fault == "audience":
            headers = verifier_env["b"]
        elif fault == "issuer":
            body["disclosed"]["issuer"] = "wrong-issuer"
        elif fault == "key":
            write_public(verifier_env["public"])
        elif fault == "challenge_expired":
            with client.app.state.vericlue.database.sessions.begin() as db:
                db.get(CredentialChallengeRow, q["id"]).expires_at = utcnow() - timedelta(seconds=1)
        elif fault == "credential_expired":
            body["disclosed"]["valid_from"] -= 120
            body["disclosed"]["valid_until"] -= 120
        elif fault == "unknown_id":
            body["challenge_id"] = encode(secrets.token_bytes(16))
        else:
            body["proof"] = body["proof"][:-1] + "B"  # Noncanonical pad bits.
        response = client.post("/v1/credentials/verify", headers=headers, json=body)
        assert response.status_code == 200 and response.json() == {"valid": False}
        assert stub_worker == []


def test_rollback_and_worker_errors_preserve_nonce(verifier_env, monkeypatch, stub_worker):
    with TestClient(create_app()) as client:
        q = challenge(client, verifier_env["a"])
        body = VerificationPresentation.model_validate(presentation(q))
        root = client.app.state.vericlue
        with pytest.raises(RuntimeError), root.database.sessions.begin() as db:
            assert CredentialVerifier(root.settings, db, A).verify(body).valid
            raise RuntimeError("synthetic transaction failure before response")
        with root.database.sessions() as db:
            assert db.get(CredentialChallengeRow, q["id"]) is not None

        def fail(*args):
            raise ApiError(503, "credential_verifier_unavailable", "Chưa sẵn sàng.")

        with monkeypatch.context() as patch:
            patch.setattr(CredentialProofWorker, "verify", fail)
            response = client.post(
                "/v1/credentials/verify",
                headers=verifier_env["a"],
                json=body.model_dump(mode="json"),
            )
            assert response.status_code == 503 and "valid" not in response.json()
        assert client.post(
            "/v1/credentials/verify", headers=verifier_env["a"], json=body.model_dump(mode="json")
        ).json()["valid"]


@pytest.mark.parametrize("clock_end", ["expired", "backwards"])
def test_clock_changes_during_crypto_and_bad_proof_do_not_consume(
    verifier_env, monkeypatch, clock_end
):
    with TestClient(create_app()) as client:
        q = challenge(client, verifier_env["a"])
        body = presentation(q)
        if clock_end == "backwards":
            with client.app.state.vericlue.database.sessions.begin() as db:
                row = db.get(CredentialChallengeRow, q["id"])
                row.issued_at -= timedelta(seconds=20)
                row.expires_at -= timedelta(seconds=20)
        monkeypatch.setattr(CredentialProofWorker, "verify", lambda *args: False)
        assert client.post(
            "/v1/credentials/verify", headers=verifier_env["a"], json=body
        ).json() == {"valid": False}

        def expired(*args):
            monkeypatch.setattr(
                "vericlue_api.services.credential_verifier.utcnow",
                lambda: (
                    utcnow() + timedelta(seconds=120)
                    if clock_end == "expired"
                    else datetime.fromtimestamp(body["disclosed"]["valid_from"] - 1, UTC)
                ),
            )
            return True

        monkeypatch.setattr(CredentialProofWorker, "verify", expired)
        assert client.post(
            "/v1/credentials/verify", headers=verifier_env["a"], json=body
        ).json() == {"valid": False}
        with client.app.state.vericlue.database.sessions() as db:
            assert db.get(CredentialChallengeRow, q["id"]) is not None


def test_capacity_and_expired_cleanup(verifier_env, monkeypatch):
    monkeypatch.setattr("vericlue_api.services.credential_verifier.MAX_PENDING_PER_AUDIENCE", 2)
    with TestClient(create_app()) as client:
        first = challenge(client, verifier_env["a"])
        challenge(client, verifier_env["a"])
        assert (
            client.post(
                "/v1/credentials/challenges", headers=verifier_env["a"], json={}
            ).status_code
            == 503
        )
        challenge(client, verifier_env["b"])
        with client.app.state.vericlue.database.sessions.begin() as db:
            db.get(CredentialChallengeRow, first["id"]).expires_at = utcnow() - timedelta(seconds=1)
        challenge(client, verifier_env["a"])
        with client.app.state.vericlue.database.sessions() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(CredentialChallengeRow)
                    .where(CredentialChallengeRow.audience == A)
                )
                == 2
            )


@pytest.mark.parametrize("credential", ["missing", "staff", "session", "duplicate"])
def test_auth_rejects_before_body_db_or_models(verifier_env, monkeypatch, credential):
    with staff_test_client(create_app()) as client:
        root = client.app.state.vericlue
        headers = {"Authorization": "Bearer wrong-session-token"}
        if credential == "missing":
            headers = {"Authorization": ""}
        elif credential == "staff":
            headers = {"Authorization": client.headers["Authorization"]}
        elif credential == "duplicate":
            headers = [("Authorization", verifier_env["a"]["Authorization"])] * 2
        monkeypatch.setattr(root.database, "sessions", lambda: pytest.fail("must reject before DB"))
        monkeypatch.setattr(root, "initialize", lambda: pytest.fail("must reject before models"))
        response = client.post("/v1/credentials/verify", headers=headers, content=b"not-json")
        assert response.status_code == 401
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "{}",
        '{"x":"http://bad.example"}',
        '{"duplicate":"https://a.example","duplicate":"https://b.example"}',
    ],
)
def test_bad_configuration_fails_closed(verifier_env, monkeypatch, value):
    monkeypatch.setenv("CREDENTIAL_VERIFIER_TOKENS", value)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        assert (
            client.post(
                "/v1/credentials/challenges", headers=verifier_env["a"], content=b"invalid"
            ).status_code
            == 503
        )


def test_bound_json_body_and_no_client_claim_injection(verifier_env):
    with TestClient(create_app()) as client:
        assert (
            client.post(
                "/v1/credentials/challenges", headers=verifier_env["a"], content=b"x" * 8193
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/v1/credentials/challenges",
                headers=verifier_env["a"],
                content=iter([b"x" * 4096] * 3),
            ).status_code
            == 413
        )
        q = challenge(client, verifier_env["a"])
        for patch in ({"nonce": q["nonce"]}, {"audience": B}, {"valid": True}):
            body = {**presentation(q), **patch}
            assert (
                client.post(
                    "/v1/credentials/verify", headers=verifier_env["a"], json=body
                ).status_code
                == 422
            )


@pytest.mark.parametrize(
    "field", ["protocol", "assurance", "verification_completed", "policy_version"]
)
def test_disclosed_wire_fields_are_required(verifier_env, stub_worker, field):
    with TestClient(create_app()) as client:
        body = presentation(challenge(client, verifier_env["a"]))
        body["disclosed"].pop(field)
        assert (
            client.post("/v1/credentials/verify", headers=verifier_env["a"], json=body).status_code
            == 422
        )
        assert stub_worker == []


def test_commit_failure_never_sends_success(verifier_env, stub_worker, monkeypatch):
    with TestClient(create_app()) as client:
        q = challenge(client, verifier_env["a"])
        root = client.app.state.vericlue
        factory = root.database.sessions

        class FailedCommit:
            @contextmanager
            def begin(self):
                with factory.begin() as db:
                    yield db
                    raise SQLAlchemyError("synthetic commit failure")

        with monkeypatch.context() as patch:
            patch.setattr(root.database, "sessions", FailedCommit())
            response = client.post(
                "/v1/credentials/verify", headers=verifier_env["a"], json=presentation(q)
            )
        assert response.status_code == 503 and "valid" not in response.json()
        with factory() as db:
            assert db.get(CredentialChallengeRow, q["id"]) is not None
        assert client.post(
            "/v1/credentials/verify", headers=verifier_env["a"], json=presentation(q)
        ).json()["valid"]


@pytest.mark.skipif(not os.environ.get("TEST_CREDENTIAL_NODE"), reason="opt-in native BBS runtime")
def test_native_issue_prove_verify_across_instances_and_audiences(verifier_env, tmp_path):
    from pydantic import SecretStr
    from test_account_auth import seeded
    from test_credential_issuance import authorize
    from test_signed_result_api import configure, ready

    node = os.environ["TEST_CREDENTIAL_NODE"]
    package = Path(__file__).resolve().parents[3] / "services/credentials"
    secret, public = tmp_path / "native-secret.json", tmp_path / "native-public.json"
    for script, args in (
        ("keygen.mjs", ["--out", str(secret)]),
        ("export-public-key.mjs", ["--key-file", str(secret), "--out", str(public)]),
    ):
        subprocess.run(
            [node, str(package / script), *args], check=True, capture_output=True, timeout=20
        )

    def holder(packet):
        process = subprocess.run(
            [node, str(Path(__file__).with_name("credential_holder.mjs"))],
            input=json.dumps(packet).encode(),
            capture_output=True,
            check=True,
            timeout=20,
        )
        return json.loads(process.stdout)

    with TestClient(create_app()) as issuer:
        root = issuer.app.state.vericlue
        root.settings = root.settings.model_copy(
            update={
                "session_privacy": True,
                "session_master_key": SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()),
            }
        )
        key, receipt, _, _ = seeded(issuer)
        configure(issuer, tmp_path)
        session, auth = ready(issuer, receipt, key)
        root.settings = root.settings.model_copy(
            update={
                "private_credentials": True,
                "credential_node": node,
                "credential_worker_file": str(package / "issuer-worker.mjs"),
                "credential_signing_key_file": str(secret),
                "credential_verifier_worker_file": str(package / "verifier-worker.mjs"),
                "credential_verifier_public_key_file": str(public),
                "credential_timeout_seconds": 10,
            }
        )
        prepared = holder({"op": "prepare"})
        request = authorize(issuer, session, auth, {**prepared["offer"], "consent": True}, key)
        response = issuer.post(
            f"/v1/sessions/{session['session_id']}/credential", headers=auth, json=request
        )
        assert response.status_code == 200, response.text
        pinned = json.loads(public.read_text(encoding="utf-8"))

        def present(q):
            return holder(
                {
                    "op": "present",
                    "key": pinned,
                    "state": prepared["state"],
                    "credential": response.json(),
                    "challenge": q,
                }
            )

        q = challenge(issuer, verifier_env["a"])
        proof = present(q)
        with TestClient(create_app()) as verifier:
            # Independent verifier needs only its public pin/runtime, not issuance keys.
            verifier.app.state.vericlue.settings = verifier.app.state.vericlue.settings.model_copy(
                update={
                    "credential_node": node,
                    "credential_verifier_worker_file": str(package / "verifier-worker.mjs"),
                    "credential_verifier_public_key_file": str(public),
                    "credential_timeout_seconds": 10,
                }
            )
            verified = verifier.post(
                "/v1/credentials/verify", headers=verifier_env["a"], json=proof
            )
            assert verified.status_code == 200 and verified.json()["valid"] is True, verified.text
            validate(verified.json(), "credential", "VerificationAccepted")
            assert verifier.app.state.vericlue.settings.private_credentials is False
            assert not verifier.app.state.vericlue.settings.credential_signing_key_file
            assert verifier.post(
                "/v1/credentials/verify", headers=verifier_env["a"], json=proof
            ).json() == {"valid": False}
            q_b = challenge(verifier, verifier_env["b"])
            proof_b = present(q_b)
            assert proof_b["pseudonym"] != proof["pseudonym"]
            assert verifier.post(
                "/v1/credentials/verify", headers=verifier_env["a"], json=proof_b
            ).json() == {"valid": False}
            assert (
                verifier.post(
                    "/v1/credentials/verify", headers=verifier_env["b"], json=proof_b
                ).json()["valid"]
                is True
            )
            q_bad = challenge(verifier, verifier_env["a"])
            bad = present(q_bad)
            bad["disclosed"]["valid_until"] -= 10
            assert verifier.post(
                "/v1/credentials/verify", headers=verifier_env["a"], json=bad
            ).json() == {"valid": False}
