"""Actual Chromium → HTTP FastAPI → native BBS, with synthetic server decisions only.

No production code, HTTP endpoint or runtime flag can seed the authorized decision.
The imported P-256 fixture key is ephemeral; this is not device enrollment/AI acceptance.
"""

import base64
import json
import os
import secrets
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Thread

import pytest
import uvicorn
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from starlette.applications import Starlette
from starlette.responses import FileResponse, HTMLResponse
from starlette.routing import Mount, Route
from test_account_auth import new_key, recovery_ready, seeded
from test_signed_result_api import configure, ready

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import CredentialChallengeRow, CredentialIssuanceRow
from vericlue_api.main import create_app

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "services/credentials"
pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_CREDENTIAL_BROWSER") != "true"
    or not os.environ.get("TEST_CREDENTIAL_NODE"),
    reason="opt-in actual Chromium, built SDK and native Node BBS runtime",
)


@pytest.fixture
def browser_client(monkeypatch):
    receivers = {name: secrets.token_urlsafe(32) for name in ("a", "b")}
    # Auth middleware captures deployment settings at app creation, as production does.
    for name, value in {
        "SESSION_PRIVACY": "true",
        "SESSION_MASTER_KEY": base64.b64encode(secrets.token_bytes(32)).decode(),
        "CREDENTIAL_VERIFIER": "true",
        "CREDENTIAL_VERIFIER_TOKENS": json.dumps(
            {token: f"https://service-{name}.example" for name, token in receivers.items()}
        ),
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client, receivers


@contextmanager
def live_holder_api(api):
    """Serve only a test harness and the existing production API on loopback."""

    async def index(request):
        return HTMLResponse(
            "<!doctype html><title>Headless HTTP holder test</title>",
            headers={
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; connect-src 'self'; base-uri 'none'",
                "Cache-Control": "no-store",
            },
        )

    async def bundle(request):
        return FileResponse(PACKAGE / "dist/holder.mjs", media_type="application/javascript")

    app = Starlette(routes=[Route("/", index), Route("/holder.mjs", bundle), Mount("/", app=api)])
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="critical", access_log=False, timeout_graceful_shutdown=2)
    )
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started, "test HTTP server did not start"
        yield origin
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive(), "test HTTP server did not stop"


@pytest.mark.parametrize("purpose", ["reauth", "recovery"])
def test_actual_browser_http_issuance_retry_and_verification(browser_client, tmp_path, purpose):
    private_client, receivers = browser_client
    node = os.environ["TEST_CREDENTIAL_NODE"]
    secret, public = tmp_path / "bbs-private.json", tmp_path / "bbs-public.json"
    for script, args in (
        ("keygen.mjs", ["--out", str(secret)]),
        ("export-public-key.mjs", ["--key-file", str(secret), "--out", str(public)]),
    ):
        subprocess.run(
            [node, str(PACKAGE / script), *args], capture_output=True, check=True, timeout=20
        )
    key, receipt, _, _ = seeded(private_client)
    configure(private_client, tmp_path)
    root = private_client.app.state.vericlue
    if purpose == "reauth":
        body, headers = ready(private_client, receipt, key)
    else:
        key = new_key()
        with root.transaction() as state:
            state.flow.settings = state.settings.model_copy(update={"use_mock_models": True})
            session = recovery_ready(state, receipt, key)
            session.created_model_mode = "real"  # Trusted historical fixture, never HTTP input.
            state.flow.settings = state.settings
            receipt = state.accounts.recover(session)
            body = {"session_id": session.session_id}
            headers = {"Authorization": "Bearer " + session.token}
    root.settings = root.settings.model_copy(
        update={
            "private_credentials": True,
            "credential_node": node,
            "credential_worker_file": str(PACKAGE / "issuer-worker.mjs"),
            "credential_signing_key_file": str(secret),
            "credential_timeout_seconds": 10,
            "credential_verifier": True,
            "credential_verifier_tokens": SecretStr(
                json.dumps(
                    {token: f"https://service-{name}.example" for name, token in receivers.items()}
                )
            ),
            "credential_verifier_issuer": "https://vericlue.example",
            "credential_verifier_public_key_file": str(public),
            "credential_verifier_worker_file": str(PACKAGE / "verifier-worker.mjs"),
        }
    )
    with root.transaction() as state:
        nonce = state.sessions.get(body["session_id"]).nonce
    packet = {
        "session_authorization": headers["Authorization"],
        "receivers": receivers,
        "device_pkcs8": base64.b64encode(
            key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        ).decode(),
        "result_key": private_client.get("/v1/result-signing-key").json(),
        "credential_key": json.loads(public.read_text(encoding="utf-8")),
        "expected": {
            "issuer": "https://vericlue.example",
            "audience": "demo-integrator",
            "session_id": body["session_id"],
            "nonce": nonce,
            "purpose": purpose,
            "account_id": receipt.account_id,
            "device_id": receipt.device_id,
        },
    }
    assert (PACKAGE / "dist/holder.mjs").is_file(), "run npm run build:holder first"
    with live_holder_api(private_client.app) as origin:
        result = subprocess.run(
            [node, str(PACKAGE / "browser-tests/http.mjs")],
            input=json.dumps({**packet, "origin": origin}).encode(),
            capture_output=True,
            timeout=50,
        )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert json.loads(result.stdout) == {
        "passed": True,
        "counts": {"authorize": 1, "issue": 2, "signs": 1},
    }
    with root.database.sessions() as db:
        assert db.scalar(select(func.count()).select_from(CredentialIssuanceRow)) == 1
        # Successful verification deletes/commits both challenges; replay had no row.
        assert db.scalar(select(func.count()).select_from(CredentialChallengeRow)) == 0
