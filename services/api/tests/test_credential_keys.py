"""Issuer key lifecycle, API trust selection and opt-in native BBS rotation."""

import importlib.util
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_accounts import private_client as private_client
from test_credential_issuance import authorize, offer, setup_credential
from test_credential_verifier import ISSUER, presentation, write_public
from test_credential_verifier import stub_worker as stub_worker
from test_credential_verifier import verifier_env as verifier_env

from vericlue_api.core.config import get_settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import (
    CredentialChallengeRow,
    CredentialKeyEventRow,
    CredentialTrustKeyRow,
)
from vericlue_api.main import create_app
from vericlue_api.schemas.credential import CredentialKey
from vericlue_api.services.credential_keys import CredentialKeyRegistry
from vericlue_api.services.credential_worker import CredentialWorker

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "vericlue_credential_keys_cli_test", ROOT / "scripts/credential_keys.py"
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.fixture
def registry_env(verifier_env, monkeypatch):
    issuer = "https://issuer-" + secrets.token_hex(6) + ".example"
    monkeypatch.setenv("CREDENTIAL_KEY_REGISTRY", "true")
    monkeypatch.setenv("CREDENTIAL_VERIFIER_ISSUER", issuer)
    get_settings.cache_clear()
    return {**verifier_env, "issuer": issuer}


def pin(path):
    return CredentialKey.model_validate_json(path.read_bytes())


def operate(client, issuer, action, value):
    with client.app.state.vericlue.database.sessions.begin() as db:
        return getattr(CredentialKeyRegistry(db, issuer), action)(value)


def register_pair(client, env, tmp_path):
    first = pin(env["public"])
    other = tmp_path / "public-other.json"
    write_public(other)
    second = pin(other)
    for public in (first, second):
        operate(client, env["issuer"], "register", public)
    operate(client, env["issuer"], "activate", first.key_id)
    return first, second


def request_challenge(client, env, key_id=None):
    body = {} if key_id is None else {"key_id": key_id}
    response = client.post("/v1/credentials/challenges", headers=env["a"], json=body)
    assert response.status_code == 200, response.text
    return response.json()


def body_for(q, issuer):
    body = presentation(q)
    body["disclosed"]["issuer"] = issuer
    return body


def test_lifecycle_is_idempotent_and_revocation_is_a_tombstone(registry_env, tmp_path):
    with TestClient(create_app()) as client:
        first, second = register_pair(client, registry_env, tmp_path)
        database = client.app.state.vericlue.database
        for _ in range(2):
            operate(client, registry_env["issuer"], "activate", second.key_id)
            operate(client, registry_env["issuer"], "register", first)
        with database.sessions() as db:
            assert db.get(CredentialTrustKeyRow, first.key_id).state == "verify_only"
            assert db.get(CredentialTrustKeyRow, second.key_id).state == "active"
            assert db.scalar(select(func.count()).select_from(CredentialKeyEventRow)) == 5
        operate(client, registry_env["issuer"], "revoke", first.key_id)
        operate(client, registry_env["issuer"], "revoke", first.key_id)
        operate(client, registry_env["issuer"], "register", first)
        with pytest.raises(ApiError):
            operate(client, registry_env["issuer"], "activate", first.key_id)
        with database.sessions() as db:
            assert db.get(CredentialTrustKeyRow, first.key_id).state == "revoked"
            assert db.scalar(select(func.count()).select_from(CredentialKeyEventRow)) == 6


def test_rotation_preserves_pending_and_selected_old_proofs_then_revocation_blocks_them(
    registry_env, tmp_path, stub_worker
):
    with TestClient(create_app()) as client:
        old, new = register_pair(client, registry_env, tmp_path)
        before = request_challenge(client, registry_env)
        old_body = body_for(before, registry_env["issuer"])
        operate(client, registry_env["issuer"], "activate", new.key_id)
        response = client.post(
            "/v1/credentials/verify",
            headers=registry_env["a"],
            json=old_body,
        )
        assert response.json()["valid"] is True
        old_pending = request_challenge(client, registry_env, old.key_id)
        current = request_challenge(client, registry_env)
        with client.app.state.vericlue.database.sessions() as db:
            assert db.get(CredentialChallengeRow, current["id"]).key_id == new.key_id
            assert db.get(CredentialChallengeRow, old_pending["id"]).key_id == old.key_id
        operate(client, registry_env["issuer"], "revoke", old.key_id)
        assert client.post(
            "/v1/credentials/verify",
            headers=registry_env["a"],
            json=body_for(old_pending, registry_env["issuer"]),
        ).json() == {"valid": False}
        assert (
            client.post(
                "/v1/credentials/challenges", headers=registry_env["a"], json={"key_id": old.key_id}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/v1/credentials/verify",
                headers=registry_env["a"],
                json=body_for(current, registry_env["issuer"]),
            ).json()["valid"]
            is True
        )
        assert len(stub_worker) == 2


@pytest.mark.parametrize("fault", ["unknown", "foreign_issuer", "no_active", "bad_hash"])
def test_registry_never_falls_back_to_the_valid_legacy_pin(registry_env, fault):
    with TestClient(create_app()) as client:
        public = pin(registry_env["public"])
        if fault == "foreign_issuer":
            operate(client, "different-issuer", "register", public)
            operate(client, "different-issuer", "activate", public.key_id)
        elif fault != "unknown":
            operate(client, registry_env["issuer"], "register", public)
            if fault == "bad_hash":
                operate(client, registry_env["issuer"], "activate", public.key_id)
                with client.app.state.vericlue.database.sessions.begin() as db:
                    db.get(CredentialTrustKeyRow, public.key_id).public_key = "A" * 128
        response = client.post("/v1/credentials/challenges", headers=registry_env["a"], json={})
        assert response.status_code == (503 if fault == "bad_hash" else 409)


def test_rollback_preserves_trust_state_and_transition_history(registry_env, tmp_path):
    with TestClient(create_app()) as client:
        old, new = register_pair(client, registry_env, tmp_path)
        database = client.app.state.vericlue.database
        with pytest.raises(RuntimeError), database.sessions.begin() as db:
            registry = CredentialKeyRegistry(db, registry_env["issuer"])
            registry.activate(new.key_id)
            registry.revoke(old.key_id)
            raise RuntimeError("synthetic operator transaction rollback")
        with database.sessions() as db:
            assert db.get(CredentialTrustKeyRow, old.key_id).state == "active"
            assert db.get(CredentialTrustKeyRow, new.key_id).state == "staged"
            assert db.scalar(select(func.count()).select_from(CredentialKeyEventRow)) == 3


def test_database_prevents_two_active_keys_for_one_issuer(registry_env, tmp_path):
    with TestClient(create_app()) as client:
        old, new = register_pair(client, registry_env, tmp_path)
        with (
            pytest.raises(IntegrityError),
            client.app.state.vericlue.database.sessions.begin() as db,
        ):
            db.get(CredentialTrustKeyRow, new.key_id).state = "active"
            db.flush()


@pytest.mark.parametrize("cutoff", ["expired", "credential_outlives_grace"])
def test_retired_key_trust_expires_and_cannot_extend_credential_lifetime(
    registry_env, tmp_path, stub_worker, cutoff
):
    with TestClient(create_app()) as client:
        old, new = register_pair(client, registry_env, tmp_path)
        q = request_challenge(client, registry_env)
        body = body_for(q, registry_env["issuer"])
        operate(client, registry_env["issuer"], "activate", new.key_id)
        with client.app.state.vericlue.database.sessions.begin() as db:
            row = db.get(CredentialTrustKeyRow, old.key_id)
            row.verify_until = (
                datetime.now(UTC) - timedelta(seconds=1)
                if cutoff == "expired"
                else datetime.fromtimestamp(body["disclosed"]["valid_until"] - 1, UTC)
            )
        response = client.post("/v1/credentials/verify", headers=registry_env["a"], json=body)
        assert response.json() == {"valid": False}
        assert stub_worker == []


def test_cli_public_only_idempotent_and_commit_before_reporting(registry_env, capsys):
    public = pin(registry_env["public"])
    base = ["--issuer", registry_env["issuer"]]
    for args in (
        ["register", "--public-key", str(registry_env["public"])],
        ["activate", "--key-id", public.key_id],
        ["list"],
        ["revoke", "--key-id", public.key_id],
        ["register", "--public-key", str(registry_env["public"])],
    ):
        assert cli.main(base + args) == 0
        output = capsys.readouterr()
        result = json.loads(output.out)
        assert len(result["keys"]) == 1
        assert "secret_key" not in output.out and "public_key" not in output.out and not output.err
    assert result["keys"][0]["state"] == "revoked"
    assert cli.main(base + ["activate", "--key-id", public.key_id]) == 2
    assert not capsys.readouterr().out


@pytest.mark.parametrize("bad", ["secret", "hash", "algorithm"])
def test_cli_rejects_private_bundles_and_invalid_public_pins(registry_env, capsys, bad):
    path = registry_env["public"]
    data = json.loads(path.read_text(encoding="utf-8"))
    if bad == "secret":
        data["secret_key"] = "not-a-key"
    elif bad == "hash":
        data["key_id"] = "0" * 64
    else:
        data["algorithm"] = "none"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert (
        cli.main(["--issuer", registry_env["issuer"], "register", "--public-key", str(path)]) == 2
    )
    assert not capsys.readouterr().out


def test_issuance_requires_current_active_key_and_checks_cached_retry(
    private_client, tmp_path, monkeypatch
):
    key, _, session, headers, calls = setup_credential(private_client, tmp_path, monkeypatch)
    root = private_client.app.state.vericlue
    public = CredentialWorker(root.settings).public_key()
    root.settings = root.settings.model_copy(update={"credential_key_registry": True})
    path = f"/v1/sessions/{session['session_id']}/credential-authorization"
    assert private_client.post(path, headers=headers, json=offer()).status_code == 503
    operate(private_client, ISSUER, "register", public)
    assert private_client.post(path, headers=headers, json=offer()).status_code == 503
    operate(private_client, ISSUER, "activate", public.key_id)
    request = authorize(private_client, session, headers, offer(), key)
    issue_path = f"/v1/sessions/{session['session_id']}/credential"
    assert private_client.post(issue_path, headers=headers, json=request).status_code == 200
    replacement_path = tmp_path / "replacement-public.json"
    write_public(replacement_path)
    replacement = pin(replacement_path)
    operate(private_client, ISSUER, "register", replacement)
    operate(private_client, ISSUER, "activate", replacement.key_id)
    assert private_client.post(issue_path, headers=headers, json=request).status_code == 503
    operate(private_client, ISSUER, "revoke", public.key_id)
    assert private_client.post(issue_path, headers=headers, json=request).status_code == 503
    assert len(calls) == 1


def test_issuer_file_switch_cannot_sign_under_a_different_context_key(
    private_client, tmp_path, monkeypatch
):
    key, _, session, headers, _ = setup_credential(private_client, tmp_path, monkeypatch)
    request = authorize(private_client, session, headers, offer(), key)
    original = CredentialWorker.issue

    def changed(self, commitment, claims):
        return original(self, commitment, claims).model_copy(update={"key_id": "f" * 64})

    monkeypatch.setattr(CredentialWorker, "issue", changed)
    response = private_client.post(
        f"/v1/sessions/{session['session_id']}/credential", headers=headers, json=request
    )
    assert response.status_code == 503
