"""Actual BBS rotation/revocation with synthetic authorized claims and a public-only verifier."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_credential_keys import ROOT, body_for, cli, pin, request_challenge
from test_credential_keys import registry_env as registry_env
from test_credential_verifier import verifier_env as verifier_env

from vericlue_api.core.config import get_settings
from vericlue_api.main import create_app


@pytest.mark.skipif(not os.environ.get("TEST_CREDENTIAL_NODE"), reason="opt-in native BBS runtime")
def test_native_rotation_revocation_and_restart(registry_env, tmp_path, monkeypatch, capsys):
    node = os.environ["TEST_CREDENTIAL_NODE"]
    package = ROOT / "services/credentials"
    monkeypatch.setenv("CREDENTIAL_NODE", node)
    monkeypatch.setenv("CREDENTIAL_VERIFIER_WORKER_FILE", str(package / "verifier-worker.mjs"))
    monkeypatch.setenv("CREDENTIAL_TIMEOUT_SECONDS", "10")
    get_settings.cache_clear()

    def run(script, args=(), packet=None):
        result = subprocess.run(
            [node, str(script), *args],
            input=json.dumps(packet).encode() if packet is not None else None,
            capture_output=True,
            check=True,
            timeout=20,
        )
        return json.loads(result.stdout) if packet is not None else None

    materials = []
    for name in ("old", "new"):
        secret, public = tmp_path / (name + "-secret.json"), tmp_path / (name + "-public.json")
        run(package / "keygen.mjs", ("--out", str(secret)))
        run(package / "export-public-key.mjs", ("--key-file", str(secret), "--out", str(public)))
        materials.append((secret, public, pin(public)))
    old, new = materials
    # Keep a valid legacy pin configured to prove that registry rejection never falls back.
    monkeypatch.setenv("CREDENTIAL_VERIFIER_PUBLIC_KEY_FILE", str(old[1]))
    get_settings.cache_clear()
    base = ["--issuer", registry_env["issuer"]]
    for _, public, _ in materials:
        assert cli.main(base + ["register", "--public-key", str(public)]) == 0
    assert cli.main(base + ["activate", "--key-id", old[2].key_id]) == 0
    holder_path = Path(__file__).with_name("credential_holder.mjs")

    with TestClient(create_app()) as client:
        before = request_challenge(client, registry_env, old[2].key_id)

        def issue(material):
            state = run(holder_path, packet={"op": "prepare"})
            # Private pipe simulates trusted server claims; no client can call it over HTTP.
            claims = {
                **body_for(before, registry_env["issuer"])["disclosed"],
                "source_result_id": "res_" + "a" * 64,
                "account_id": "acct_" + "b" * 32,
                "device_id": "dev_" + "c" * 32,
                "source_purpose": "reauth",
            }
            credential = run(
                package / "issuer-worker.mjs",
                ("--key-file", str(material[0])),
                {"commitment": state["offer"]["commitment"], "claims": claims},
            )
            return state, credential

        def present(material, issued, q):
            state, credential = issued
            return run(
                holder_path,
                packet={
                    "op": "present",
                    "key": material[2].model_dump(mode="json"),
                    "state": state["state"],
                    "credential": credential,
                    "challenge": q,
                },
            )

        old_issued = issue(old)
        pending = present(old, old_issued, before)
        assert cli.main(base + ["activate", "--key-id", new[2].key_id]) == 0
        assert (
            client.post("/v1/credentials/verify", headers=registry_env["a"], json=pending).json()[
                "valid"
            ]
            is True
        )
        old_q = request_challenge(client, registry_env, old[2].key_id)
        old_proof = present(old, old_issued, old_q)
        new_q = request_challenge(client, registry_env)
        wrong_key = present(old, old_issued, new_q)
        assert client.post(
            "/v1/credentials/verify", headers=registry_env["a"], json=wrong_key
        ).json() == {"valid": False}
        new_issued = issue(new)
        new_proof = present(new, new_issued, new_q)
        assert cli.main(base + ["revoke", "--key-id", old[2].key_id]) == 0
        assert client.post(
            "/v1/credentials/verify", headers=registry_env["a"], json=old_proof
        ).json() == {"valid": False}
        assert (
            client.post(
                "/v1/credentials/challenges",
                headers=registry_env["a"],
                json={"key_id": old[2].key_id},
            ).status_code
            == 409
        )
    with TestClient(create_app()) as restarted:
        assert not restarted.app.state.vericlue.settings.credential_signing_key_file
        assert restarted.post(
            "/v1/credentials/verify", headers=registry_env["a"], json=old_proof
        ).json() == {"valid": False}
        result = restarted.post("/v1/credentials/verify", headers=registry_env["a"], json=new_proof)
        assert result.status_code == 200 and result.json()["valid"] is True, result.text
    output = capsys.readouterr()
    assert "secret_key" not in output.out and "holderSecret" not in output.out
