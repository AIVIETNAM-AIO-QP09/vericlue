"""Real P-256/DB/HTTP security tests with synthetic biometrics, not accuracy evidence."""

import base64
import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select
from test_accounts import prepared, real_settings
from test_accounts import private_client as private_client

from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import (
    AccountRecoveryRow,
    AccountRow,
    DeviceProofUseRow,
    SessionRow,
    utcnow,
)
from vericlue_api.services.account_auth import AccountAuth, message
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.identity_steps import _digest
from vericlue_ml.common.result import Evidence, Module
from vericlue_ml.face.enrolled import RECOVERY_MATCH_VERSION


def new_key():
    return ec.generate_private_key(ec.SECP256R1())


def spki(key):
    return base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode()


def signed(key, payload):
    return base64.b64encode(key.sign(payload, ec.ECDSA(hashes.SHA256()))).decode()


def seeded(client):
    key = new_key()
    with client.app.state.vericlue.transaction() as state:
        with patch("test_accounts.ec.generate_private_key", return_value=key):
            session, template, continuity = prepared(state)
        session.phone_hmac = _digest(state.settings.id_hmac_key.get_secret_value(), "0901234567")
        receipt = AccountStore(real_settings(state), state.db).create(
            session,
            template,
            continuity=continuity,
        )
        return key, receipt, session.session_id, {"Authorization": "Bearer " + session.token}


def start(client, receipt, *, recovery_key=None):
    request = {
        "purpose": "recovery" if recovery_key else "reauth",
        "nonce": "account_auth_synthetic_nonce",
        "account_id": receipt.account_id,
    }
    if recovery_key:
        request["device_public_key_spki"] = spki(recovery_key)
    else:
        request["device_id"] = receipt.device_id
    response = client.post("/v1/sessions", json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    return body, {"Authorization": "Bearer " + body["token"]}


def test_receipt_is_session_authorized_minimal_and_not_cached(private_client):
    _, receipt, sid, headers = seeded(private_client)
    path = f"/v1/sessions/{sid}/account"
    response = private_client.get(path, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["account_id"] == receipt.account_id
    assert set(response.json()) == {"account_id", "device_id", "expires_at"}
    assert private_client.get(path).status_code == 401
    other = private_client.post("/v1/sessions").json()
    assert (
        private_client.get(path, headers={"Authorization": "Bearer " + other["token"]}).status_code
        == 401
    )
    assert (
        private_client.get(
            f"/v1/sessions/{other['session_id']}/account",
            headers={
                "Authorization": "Bearer " + other["token"],
            },
        ).status_code
        == 409
    )


def test_l0_real_signature_persists_once_and_never_grants_biometric_pass(private_client):
    key, receipt, _, _ = seeded(private_client)
    body, headers = start(private_client, receipt)
    sid = body["session_id"]
    payload = base64.b64decode(body["device_challenge"]["message"])
    context = json.loads(payload)
    assert context["account_id"] == receipt.account_id
    assert context["device_id"] == receipt.device_id
    path = f"/v1/sessions/{sid}/device-proof"
    signature = signed(key, payload)
    assert private_client.post(path, json={"signature": signature}).status_code == 401
    assert private_client.post(path, headers=headers, json={"signature": signature}).json() == {
        "received": True
    }
    assert (
        private_client.post(path, headers=headers, json={"signature": signature}).status_code == 409
    )
    with private_client.app.state.vericlue.transaction() as state:
        assert state.sessions.get(sid).device_verified
        assert state.db.get(SessionRow, sid).status == "incomplete"
        assert state.db.scalar(select(func.count()).select_from(DeviceProofUseRow)) == 1
    # No mock face or voice can turn a registered device into an accepted account session.
    assert (
        private_client.post(
            f"/v1/sessions/{sid}/signals",
            headers=headers,
            json={
                "challenge_id": body["challenge"]["challenge_id"],
                "color_events": [],
                "frame_times": [],
            },
        ).status_code
        == 503
    )
    assert private_client.post(f"/v1/sessions/{sid}/challenge", headers=headers).status_code == 200


@pytest.mark.parametrize(
    "fault", ["wrong_key", "other_session", "tampered", "expired", "bad_base64"]
)
def test_l0_rejects_untrusted_proof_without_claim_or_verdict(private_client, fault):
    key, receipt, _, _ = seeded(private_client)
    body, headers = start(private_client, receipt)
    sid = body["session_id"]
    payload = base64.b64decode(body["device_challenge"]["message"])
    if fault == "wrong_key":
        key = new_key()
    elif fault == "tampered":
        payload = payload.replace(b"reauth", b"recovery")
    elif fault == "other_session":
        other, _ = start(private_client, receipt)
        payload = base64.b64decode(other["device_challenge"]["message"])
    elif fault == "expired":
        with private_client.app.state.vericlue.transaction() as state:
            state.sessions.get(sid).device_auth_expires_ms = 1
    signature = "!!!!!!!!" if fault == "bad_base64" else signed(key, payload)
    response = private_client.post(
        f"/v1/sessions/{sid}/device-proof", headers=headers, json={"signature": signature}
    )
    assert response.status_code == 409
    with private_client.app.state.vericlue.transaction() as state:
        assert not state.sessions.get(sid).device_verified
        assert state.db.get(DeviceProofUseRow, sid) is None
        assert state.db.get(SessionRow, sid).status == "incomplete"


def test_client_cannot_supply_registered_key_or_device_verified(private_client):
    key, receipt, _, _ = seeded(private_client)
    request = {
        "purpose": "reauth",
        "nonce": "synthetic_nonce_12345",
        "account_id": receipt.account_id,
        "device_id": receipt.device_id,
    }
    assert (
        private_client.post("/v1/sessions", json={**request, "device_verified": True}).status_code
        == 422
    )
    assert (
        private_client.post(
            "/v1/sessions", json={**request, "device_public_key_spki": spki(key)}
        ).status_code
        == 503
    )
    assert (
        private_client.post(
            "/v1/sessions", json={**request, "device_id": "dev_" + "f" * 32}
        ).status_code
        == 409
    )


def test_recovery_otp_must_use_registered_phone_before_sending(private_client):
    _, receipt, _, _ = seeded(private_client)
    body, headers = start(private_client, receipt, recovery_key=new_key())
    sid = body["session_id"]
    wrong = private_client.post(
        f"/v1/sessions/{sid}/otp", headers=headers, json={"phone": "0901111111"}
    )
    assert wrong.status_code == 409 and "simulated_sms" not in wrong.text
    with private_client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        assert session.otp_sends == 0 and session.otp_hash is None
    correct = private_client.post(
        f"/v1/sessions/{sid}/otp", headers=headers, json={"phone": "0901234567"}
    )
    assert correct.status_code == 200 and "simulated_sms" in correct.json()
    # Demo SMS is explicitly simulated. It cannot open account biometrics or rotate a key.
    assert (
        private_client.post(
            f"/v1/sessions/{sid}/finalize",
            headers=headers,
            json={"challenge_id": body["challenge"]["challenge_id"]},
        ).status_code
        == 503
    )


def recovery_ready(state, receipt, key):
    with patch("test_accounts.ec.generate_private_key", return_value=key):
        session, _, continuity = prepared(state, id_hmac="e" * 64)
    session.purpose = "recovery"
    session.account_id = receipt.account_id
    session.registered_device_id = receipt.device_id
    session.phone_hmac = state.db.get(AccountRow, receipt.account_id).phone_hmac
    session.id_confirmed = False  # Recovery compares the enrolled face, not a fresh card.
    session.results[Module.FACE_CONTINUITY] = continuity
    match = session.results[Module.FACE_MATCH]
    match.model_version = RECOVERY_MATCH_VERSION
    match.quality["enrolled_reference"] = True
    match.evidence.append(
        Evidence(type="text", name="reference_account_id", value=receipt.account_id)
    )
    # prepared signed onboarding manifests: re-sign after changing the purpose.
    from sqlalchemy import delete

    from vericlue_api.db.models import MediaProofUseRow
    from vericlue_api.services.media_proof import manifest

    state.db.execute(
        delete(MediaProofUseRow).where(MediaProofUseRow.session_id == session.session_id)
    )
    from vericlue_api.services.media_proof import verify_and_consume

    for stage in ("face", "voice"):
        files = {
            "image" if stage == "face" else "audio": (
                "test.jpg" if stage == "face" else "test.wav",
                b"synthetic",
            ),
            "video": ("test.mp4", b"synthetic"),
        }
        payload, _, _ = manifest(session, stage, files)
        verify_and_consume(state.db, session, stage, signed(key, payload), files, required=True)
    return session


def test_recovery_reseals_original_template_revokes_old_sessions_and_keeps_ttl(private_client):
    old_key, receipt, _, _ = seeded(private_client)
    body, headers = start(private_client, receipt)
    sid = body["session_id"]
    signature = signed(old_key, base64.b64decode(body["device_challenge"]["message"]))
    assert (
        private_client.post(
            f"/v1/sessions/{sid}/device-proof", headers=headers, json={"signature": signature}
        ).status_code
        == 200
    )
    new = new_key()
    with private_client.app.state.vericlue.transaction() as state:
        store = AccountStore(real_settings(state), state.db)
        before = store.get(receipt.account_id)
        recovery = recovery_ready(state, receipt, new)
        recovered = store.recover(recovery)
        assert store.recover(recovery) == recovered  # Same completed recovery is idempotent.
        after = store.get(receipt.account_id)
        assert after.template == before.template
        assert after.public_key_spki == spki(new) and recovered.device_id != receipt.device_id
        assert recovered.expires_at == receipt.expires_at
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 1
        assert (
            state.db.get(AccountRecoveryRow, recovery.session_id).previous_device_id
            == receipt.device_id
        )
        with pytest.raises(ApiError):
            AccountAuth(store).require_verified(state.sessions.get(sid))
        recovery_sid, token = recovery.session_id, recovery.token
    assert private_client.post(f"/v1/sessions/{sid}/challenge", headers=headers).status_code == 409
    response = private_client.get(
        f"/v1/sessions/{recovery_sid}/account", headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 200 and response.json()["device_id"] == recovered.device_id
    start(private_client, recovered)  # New key is now the server's enrolled reference.


@pytest.mark.parametrize(
    "fault", ["otp", "phone", "match", "scope", "continuity", "old_device", "mixed", "expired"]
)
def test_recovery_rejects_incomplete_evidence_and_does_not_replace_key(private_client, fault):
    key, receipt, _, _ = seeded(private_client)
    with private_client.app.state.vericlue.transaction() as state:
        session = recovery_ready(state, receipt, new_key())
        settings = real_settings(state)
        if fault == "otp":
            session.otp_verified = False
        elif fault == "phone":
            session.phone_hmac = "0" * 64
        elif fault == "match":
            session.results[Module.FACE_MATCH].status = "degraded"
        elif fault == "scope":
            session.results[Module.FACE_MATCH].evidence.pop()
        elif fault == "continuity":
            session.results.pop(Module.FACE_CONTINUITY)
        elif fault == "old_device":
            session.registered_device_id = "dev_" + "0" * 32
        elif fault == "mixed":
            settings = settings.model_copy(update={"use_mock_models": "mixed"})
        elif fault == "expired":
            session.token_expires_at = utcnow() - timedelta(seconds=1)
        store = AccountStore(settings, state.db)
        with pytest.raises(ApiError):
            store.recover(session)
        assert store.get(receipt.account_id).public_key_spki == spki(key)
        assert state.db.get(AccountRecoveryRow, session.session_id) is None


def test_bare_verified_flag_without_db_claim_is_not_l0(private_client):
    _, receipt, _, _ = seeded(private_client)
    body, _ = start(private_client, receipt)
    with private_client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(body["session_id"])
        session.device_verified = True
        assert len(hashlib.sha256(message(session)).hexdigest()) == 64
        with pytest.raises(ApiError):
            state.flow.account_auth.require_verified(session)


@pytest.mark.parametrize("mode", [False, "mixed"])
def test_l0_can_run_in_real_mode_but_cannot_open_biometrics(private_client, mode):
    key, receipt, _, _ = seeded(private_client)
    root = private_client.app.state.vericlue
    root.settings = root.settings.model_copy(update={"use_mock_models": mode})
    body, headers = start(private_client, receipt)
    signature = signed(key, base64.b64decode(body["device_challenge"]["message"]))
    assert (
        private_client.post(
            f"/v1/sessions/{body['session_id']}/device-proof",
            headers=headers,
            json={"signature": signature},
        ).status_code
        == 200
    )
    assert (
        private_client.post(
            f"/v1/sessions/{body['session_id']}/finalize",
            headers=headers,
            json={"challenge_id": body["challenge"]["challenge_id"]},
        ).status_code
        == 503
    )


def test_recovery_transaction_failure_preserves_old_key(private_client):
    key, receipt, _, _ = seeded(private_client)
    root = private_client.app.state.vericlue
    with pytest.raises(RuntimeError), root.transaction() as state:
        store = AccountStore(real_settings(state), state.db)
        session = recovery_ready(state, receipt, new_key())
        store.recover(session)
        raise RuntimeError("synthetic outer transaction failure")
    with root.transaction() as state:
        store = AccountStore(real_settings(state), state.db)
        assert store.get(receipt.account_id).public_key_spki == spki(key)
        assert state.db.scalar(select(func.count()).select_from(AccountRecoveryRow)) == 0
