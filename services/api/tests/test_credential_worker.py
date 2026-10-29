"""Worker fault boundaries; native crypto/HTTP round trip lives in test_credential_issuance."""

import io
import json
import subprocess

import pytest
from test_accounts import private_client as private_client
from test_credential_issuance import REAL_ISSUE, setup_credential

from vericlue_api.core.errors import ApiError
from vericlue_api.core.signing import encode
from vericlue_api.schemas.credential import VerificationClaims, VerificationCredential
from vericlue_api.services.credential_worker import _SLOT, CredentialWorker


@pytest.mark.parametrize(
    "fault",
    ["success", "timeout", "oversize", "malformed", "wrong_key", "wrong_claim", "exit_error"],
)
def test_bounded_worker_rejects_invalid_outputs_and_releases_slot(
    private_client, tmp_path, monkeypatch, fault
):
    setup_credential(private_client, tmp_path, monkeypatch)
    worker = CredentialWorker(private_client.app.state.vericlue.settings)
    claims = VerificationClaims(
        issuer="https://vericlue.example",
        valid_from=1793059200,
        valid_until=1793059260,
        source_result_id="res_" + "a" * 64,
        account_id="acct_" + "b" * 32,
        device_id="dev_" + "c" * 32,
        source_purpose="reauth",
    )
    result = VerificationCredential(
        claims=claims,
        signature=encode(bytes(80)),
        signer_entropy="1" * 64,
        key_id=worker.public_key().key_id,
    )
    value = result.model_dump(mode="json")
    if fault == "wrong_key":
        value["key_id"] = "f" * 64
    if fault == "wrong_claim":
        value["claims"]["account_id"] = "acct_" + "d" * 32
    raw = json.dumps(value).encode()
    if fault == "oversize":
        raw = b"x" * 9000
    if fault == "malformed":
        raw = b"not-json"
    captured = {}

    class Process:
        returncode = None
        stdin = io.BytesIO()
        stdout = io.BytesIO(raw)

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout):
            if fault == "timeout" and self.returncode is None:
                raise subprocess.TimeoutExpired("synthetic-worker", timeout)
            if self.returncode is None:
                self.returncode = 1 if fault == "exit_error" else 0
            return self.returncode

    process = Process()

    def spawn(args, **kwargs):
        captured.update(kwargs)
        assert args[1].endswith("issuer-worker.mjs")
        return process

    monkeypatch.setattr("vericlue_api.services.credential_worker.subprocess.Popen", spawn)
    monkeypatch.setenv("NODE_OPTIONS", "synthetic-do-not-forward")
    if fault == "success":
        assert REAL_ISSUE(worker, encode(bytes(176)), claims) == result
    else:
        with pytest.raises(ApiError) as caught:
            REAL_ISSUE(worker, encode(bytes(176)), claims)
        assert caught.value.error_code == "credential_unavailable"
    assert _SLOT.acquire(blocking=False)
    _SLOT.release()
    assert "NODE_OPTIONS" not in captured["env"]
    assert "SESSION_MASTER_KEY" not in captured["env"]
    assert "STAFF_ACCESS_TOKENS" not in captured["env"]
    assert captured["stderr"] == subprocess.DEVNULL
