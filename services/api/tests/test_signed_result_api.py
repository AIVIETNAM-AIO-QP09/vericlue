"""Signed real-decision handoff tested with synthetic server verdicts and actual keys/DB.

Fixtures inject historical completed decisions, never open the real dynamic flow.
No HTTP client can manufacture those verdicts, an account or a positive assertion.
"""

import base64
import json
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from test_account_auth import new_key, recovery_ready, seeded, signed, start
from test_accounts import private_client as private_client
from test_accounts import real_settings, verdict

from vericlue_api.core.signing import decode, verify_result
from vericlue_api.db.models import DecisionRow, DeviceProofUseRow, SessionRow, utcnow
from vericlue_api.schemas.result import SignedResult
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.media_proof import manifest, verify_and_consume
from vericlue_ml.common.result import Evidence, Module
from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION


def configure(client, tmp_path):
    signing = Ed25519PrivateKey.generate()
    private = tmp_path / "result-private.pem"
    private.write_bytes(
        signing.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    root = client.app.state.vericlue
    with root.transaction() as state:
        settings = real_settings(state).model_copy(
            update={
                "result_signing_key_file": str(private),
                "result_issuer": "https://vericlue.example",
                "result_audience": "demo-integrator",
            }
        )
    root.settings = settings
    return signing


def ready(client, receipt, key):
    body, headers = start(client, receipt)
    sid = body["session_id"]
    proof = signed(key, base64.b64decode(body["device_challenge"]["message"]))
    assert (
        client.post(
            f"/v1/sessions/{sid}/device-proof", headers=headers, json={"signature": proof}
        ).status_code
        == 200
    )
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        session.results = {
            m: verdict(m)
            for m in (
                Module.QUALITY,
                Module.CHROMAPULSE,
                Module.CAMPROBE,
                Module.FACE_PAD,
                Module.FACE_DEEPFAKE,
            )
        }
        session.results[Module.FACE_MATCH] = verdict(
            Module.FACE_MATCH,
            REAUTH_MATCH_VERSION,
            quality={"enrolled_reference": True},
            evidence=[
                Evidence(type="text", name="reference_account_id", value=receipt.account_id),
            ],
        )
        files = {"image": ("synthetic.jpg", b"synthetic"), "video": ("synthetic.mp4", b"synthetic")}
        payload, _, _ = manifest(session, "face", files)
        verify_and_consume(state.db, session, "face", signed(key, payload), files, required=True)
        session.accepted_steps = ["media", "signals", "finalize"]
        session.completed = True
        state.sessions.record_decision(
            session, "pass", thresholds={}, config_version="synthetic-test"
        )
    return body, headers


def test_public_key_without_session_auth_and_without_db_initialization(
    private_client, tmp_path, monkeypatch
):
    signing = configure(private_client, tmp_path)
    root = private_client.app.state.vericlue
    monkeypatch.setattr(
        root, "initialize", lambda: pytest.fail("Public key must not load models or access DB")
    )
    response = private_client.get("/v1/result-signing-key")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"algorithm", "key_id", "public_key_spki"}
    key = serialization.load_der_public_key(base64.b64decode(response.json()["public_key_spki"]))
    assert key.public_bytes_raw() == signing.public_key().public_bytes_raw()
    assert "private" not in response.text.lower()


def test_signed_committed_pass_is_stable_and_context_bound(private_client, tmp_path):
    key, receipt, _, _ = seeded(private_client)
    signing = configure(private_client, tmp_path)
    body, headers = ready(private_client, receipt, key)
    path = f"/v1/sessions/{body['session_id']}/result"
    assert private_client.get(path).status_code == 401
    first = private_client.get(path, headers=headers)
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert private_client.get(path, headers=headers).json() == first.json()
    assert (
        private_client.get(
            path + "?audience=attacker&status=deny&nonce=attacker", headers=headers
        ).json()
        == first.json()
    )
    envelope = SignedResult.model_validate(first.json())
    claims = verify_result(
        envelope,
        signing.public_key(),
        issuer="https://vericlue.example",
        audience="demo-integrator",
        session_id=body["session_id"],
        nonce=body["nonce"],
        purpose="reauth",
        now=int(utcnow().timestamp()),
    )
    assert claims.status == "pass" and claims.account_id == receipt.account_id
    assert claims.expires_at - claims.issued_at <= 60
    raw = decode(envelope.payload).decode()
    for forbidden in (
        "embedding",
        "score",
        "prob_attack",
        "phone",
        "id_number",
        "public_key",
        "synthetic-storage-test",
    ):
        assert forbidden not in raw


@pytest.mark.parametrize(
    "fault",
    [
        "mock",
        "mixed",
        "incomplete",
        "review",
        "deleted",
        "latest_decision",
        "expired_decision",
        "missing_match",
        "degraded",
        "probability",
        "protocol",
        "scope",
        "unverified",
        "claim_missing",
        "voice_owed",
        "origin_mode",
        "audience_changed",
        "issuer_changed",
        "legacy_binding",
    ],
)
def test_ineligible_results_cannot_be_certified(private_client, tmp_path, fault):
    key, receipt, _, _ = seeded(private_client)
    configure(private_client, tmp_path)
    body, headers = ready(private_client, receipt, key)
    root = private_client.app.state.vericlue
    with root.transaction() as state:
        session = state.sessions.get(body["session_id"])
        row = state.db.get(SessionRow, session.session_id)
        if fault == "mock":
            session.results[Module.FACE_PAD].model_version = "mock@0.1"
        elif fault == "mixed":
            root.settings = root.settings.model_copy(update={"use_mock_models": "mixed"})
        elif fault == "incomplete":
            session.completed = False
        elif fault == "review":
            row.ever_review = True
        elif fault == "deleted":
            row.media_deleted_at = utcnow()  # SessionStore refreshes it; use expiry below too.
        elif fault == "latest_decision":
            row.status = "deny"
        elif fault == "expired_decision":
            state.db.scalar(
                select(DecisionRow)
                .where(DecisionRow.session_id == session.session_id)
                .order_by(DecisionRow.id.desc())
            ).created_at -= timedelta(seconds=61)
        elif fault == "missing_match":
            session.results.pop(Module.FACE_MATCH)
        elif fault == "degraded":
            session.results[Module.QUALITY].status = "degraded"
        elif fault == "probability":
            session.results[Module.FACE_PAD].prob_attack = None
        elif fault == "protocol":
            session.results[Module.FACE_MATCH].model_version = "old-protocol"
        elif fault == "scope":
            session.results[Module.FACE_MATCH].evidence = []
        elif fault == "unverified":
            session.device_verified = False
        elif fault == "claim_missing":
            state.db.delete(state.db.get(DeviceProofUseRow, session.session_id))
        elif fault == "voice_owed":
            session.voice_owed = True
        elif fault == "origin_mode":
            session.created_model_mode = "mock"
        elif fault == "audience_changed":
            root.settings = root.settings.model_copy(update={"result_audience": "other-integrator"})
        elif fault == "issuer_changed":
            root.settings = root.settings.model_copy(update={"result_issuer": "other-issuer"})
        elif fault == "legacy_binding":
            session.result_audience = None
    if fault == "deleted":
        # Model storage cleanup, without loading the domain snapshot (save_all resets activity).
        with root.database.sessions.begin() as db:
            db.get(SessionRow, body["session_id"]).media_deleted_at = utcnow()
    response = private_client.get(f"/v1/sessions/{body['session_id']}/result", headers=headers)
    assert response.status_code == 409, response.text


def test_fetch_does_not_refresh_expiry_and_expired_decision_is_not_resigned(
    private_client, tmp_path, monkeypatch
):
    key, receipt, _, _ = seeded(private_client)
    configure(private_client, tmp_path)
    body, headers = ready(private_client, receipt, key)
    path = f"/v1/sessions/{body['session_id']}/result"
    envelope = private_client.get(path, headers=headers).json()
    exp = json.loads(decode(envelope["payload"]))["expires_at"]
    from datetime import UTC, datetime

    monkeypatch.setattr(
        "vericlue_api.services.signed_results.utcnow", lambda: datetime.fromtimestamp(exp, UTC)
    )
    assert private_client.get(path, headers=headers).status_code == 409


@pytest.mark.parametrize("status", ["deny", "recovery_required"])
def test_valid_signature_preserves_negative_decision(private_client, tmp_path, status):
    key, receipt, _, _ = seeded(private_client)
    signing = configure(private_client, tmp_path)
    body, headers = ready(private_client, receipt, key)
    with private_client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(body["session_id"])
        state.sessions.record_decision(
            session, status, thresholds={}, config_version="synthetic-negative"
        )
    response = private_client.get(f"/v1/sessions/{body['session_id']}/result", headers=headers)
    assert response.status_code == 200
    value = verify_result(
        SignedResult.model_validate(response.json()),
        signing.public_key(),
        issuer="https://vericlue.example",
        audience="demo-integrator",
        session_id=body["session_id"],
        nonce=body["nonce"],
        purpose="reauth",
        now=int(utcnow().timestamp()),
    )
    assert value.status == status and value.account_id is value.device_id is None


def test_recovery_assertion_binds_new_device_and_revokes_old_assertion_issuance(
    private_client, tmp_path
):
    key, receipt, _, _ = seeded(private_client)
    signing = configure(private_client, tmp_path)
    body, headers = ready(private_client, receipt, key)
    with private_client.app.state.vericlue.transaction() as state:
        # Trusted fixture only: provision the synthetic full-stage verdicts while HTTP stays guarded.
        state.flow.settings = state.settings.model_copy(update={"use_mock_models": True})
        session = recovery_ready(state, receipt, new_key())
        session.created_model_mode = "real"  # Synthetic historical server decision, never HTTP.
        state.flow.settings = state.settings
        recovered = AccountStore(state.settings, state.db).recover(session)
        sid, token = session.session_id, session.token
    response = private_client.get(
        f"/v1/sessions/{sid}/result", headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 200, response.text
    raw = json.loads(decode(response.json()["payload"]))
    result = verify_result(
        SignedResult.model_validate(response.json()),
        signing.public_key(),
        issuer=raw["issuer"],
        audience=raw["audience"],
        session_id=sid,
        nonce=raw["nonce"],
        purpose="recovery",
        now=int(utcnow().timestamp()),
    )
    assert result.device_id == recovered.device_id != receipt.device_id
    assert (
        private_client.get(f"/v1/sessions/{body['session_id']}/result", headers=headers).status_code
        == 409
    )


@pytest.mark.parametrize("fault", ["unconfigured", "missing_file", "wrong_key"])
def test_unconfigured_or_invalid_signer_fails_closed(private_client, tmp_path, fault):
    if fault != "unconfigured":
        configure(private_client, tmp_path)
        root = private_client.app.state.vericlue
        path = tmp_path / "missing.pem"
        if fault == "wrong_key":
            path.write_bytes(b"synthetic-not-a-private-key")
        root.settings = root.settings.model_copy(update={"result_signing_key_file": str(path)})
    response = private_client.get("/v1/result-signing-key")
    assert response.status_code == 503
    assert "synthetic-not-a-private-key" not in response.text and str(tmp_path) not in response.text
