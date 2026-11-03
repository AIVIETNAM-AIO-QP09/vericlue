"""HTTP/crypto security tests use synthetic verdicts, never biometric accuracy claims."""

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy import select
from test_account_auth import new_key, recovery_ready, signed, spki
from test_accounts import prepared, real_settings, verdict
from test_accounts import private_client as private_client

from vericlue_api.db.models import (
    AccountAccessAttemptRow,
    AccountAccessCredentialRow,
    AccountAccessTokenRow,
    AccountRow,
    DeviceProofUseRow,
    SessionRow,
    utcnow,
)
from vericlue_api.schemas.session import CreateSessionRequest
from vericlue_api.services.account_auth import AccountAuth, message
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.media_proof import manifest, verify_and_consume
from vericlue_ml.common.result import Evidence, Module
from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION

PASSWORD = "Synthetic-password-2026"
SETUP = {
    "username": "synthetic.user",
    "password": PASSWORD,
    "profile_consent": True,
    "policy_version": "account-profile-v1",
}


@pytest.fixture
def enrolled(private_client):
    root = private_client.app.state.vericlue
    key = new_key()
    with root.transaction() as state:
        with patch("test_accounts.ec.generate_private_key", return_value=key):
            session, template, continuity = prepared(state)
        receipt = AccountStore(real_settings(state), state.db).create(
            session, template, continuity=continuity
        )
        session.created_model_mode = "real"
        session.id_confirmed_fields = {"full_name": "NGUYEN VAN SYNTHETIC"}
        session.sensitive_confirmed_id_number = "012345678901"
        sid, token = session.session_id, session.token
        settings = real_settings(state).model_copy(
            update={
                "product_mode": "ekyc",
                "account_enrollment": True,
                "account_access_enabled": True,
            }
        )
    root.settings = settings
    return private_client, receipt, sid, {"Authorization": "Bearer " + token}, key


def setup(enrolled):
    client, _, sid, headers, _ = enrolled
    result = client.post(f"/v1/sessions/{sid}/account-access/setup", headers=headers, json=SETUP)
    assert result.status_code == 200, result.text
    return result.json()


def login(client, password=PASSWORD, username=SETUP["username"]):
    return client.post(
        "/v1/account-access/password", json={"username": username, "password": password}
    )


def access_header(result):
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def validate_contract(value, definition):
    schema = json.loads(
        (
            Path(__file__).parents[3] / "packages/contracts/schemas/account_access.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator({"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]}).validate(
        value
    )


def test_setup_password_profile_logout_and_encrypted_storage(enrolled):
    client, receipt, sid, headers, _ = enrolled
    profile = setup(enrolled)
    validate_contract(profile, "AccountProfile")
    assert profile["full_name"] == "NGUYEN VAN SYNTHETIC"
    assert profile["masked_id_number"] == "********8901"
    assert "access_token" not in profile
    again = client.post(f"/v1/sessions/{sid}/account-access/setup", headers=headers, json=SETUP)
    assert again.json() == profile
    response = login(client)
    assert response.status_code == 200, response.text
    validate_contract(response.json(), "AccountAccessSession")
    assert response.json()["authentication_method"] == "password"
    auth = access_header(response)
    assert client.get("/v1/account-access/me", headers=auth).json() == profile
    assert client.get("/v1/account-access/me", headers=headers).status_code == 401
    assert client.get(f"/v1/sessions/{sid}/account", headers=auth).status_code == 401
    with client.app.state.vericlue.transaction() as state:
        row = state.db.get(AccountAccessCredentialRow, receipt.account_id)
        stored = repr(vars(row))
        for secret in (PASSWORD, SETUP["username"], profile["full_name"], "012345678901"):
            assert secret not in stored
        token = response.json()["access_token"]
        assert state.db.get(AccountAccessTokenRow, hashlib.sha256(token.encode()).hexdigest())
        assert token not in repr(vars(state.db.scalar(select(AccountAccessTokenRow))))
    assert response.headers["cache-control"] == "no-store"
    assert client.post("/v1/account-access/logout", headers=auth).json() == {"revoked": True}
    assert client.get("/v1/account-access/me", headers=auth).status_code == 401


def test_failed_password_attempts_commit_and_lock_across_requests(enrolled):
    client = enrolled[0]
    setup(enrolled)
    unknown = login(client, username="does.not.exist")
    wrong = login(client, password="Wrong-password-2026")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    for _ in range(4):
        assert login(client, password="Wrong-password-2026").status_code == 401
    assert login(client).status_code == 401
    with client.app.state.vericlue.transaction() as state:
        rows = list(state.db.scalars(select(AccountAccessAttemptRow)))
        assert any(row.attempts == 5 for row in rows)
        for row in rows:
            row.window_started_at = utcnow() - timedelta(minutes=6)
    assert login(client).status_code == 200


@pytest.mark.parametrize("fault", ["incomplete", "review", "mock", "voice_owed"])
def test_setup_requires_actual_completed_enrollment(enrolled, fault):
    client, _, sid, headers, _ = enrolled
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        if fault == "incomplete":
            session.completed = False
        elif fault == "review":
            state.db.get(SessionRow, sid).ever_review = True
        elif fault == "mock":
            session.created_model_mode = "mock"
        else:
            session.voice_owed = True
    response = client.post(f"/v1/sessions/{sid}/account-access/setup", headers=headers, json=SETUP)
    assert response.status_code == 409, response.text


def test_expiry_and_account_device_rotation_invalidate_access(enrolled):
    client, receipt, _, _, _ = enrolled
    setup(enrolled)
    auth = access_header(login(client))
    with client.app.state.vericlue.transaction() as state:
        state.db.get(AccountRow, receipt.account_id).device_id = "dev_rotated"
    assert client.get("/v1/account-access/me", headers=auth).status_code == 401
    assert login(client).status_code == 401
    with client.app.state.vericlue.transaction() as state:
        state.db.get(AccountRow, receipt.account_id).expires_at = utcnow() - timedelta(seconds=1)
        state.accounts.expire()
        row = state.db.get(AccountAccessCredentialRow, receipt.account_id)
        assert row.wrapped_key is row.encrypted_payload is row.username_hmac is None
        assert state.db.scalar(select(AccountAccessTokenRow)).revoked_at is not None


def face_session(enrolled):
    client, receipt, _, _, key = enrolled
    root = client.app.state.vericlue
    # Create under synthetic settings, then inject trusted test evidence. No HTTP gate is bypassed.
    original = root.settings
    root.settings = original.model_copy(
        update={"use_mock_models": True, "account_enrollment": False}
    )
    with root.transaction() as state:
        created = state.flow.create(
            "genuine",
            CreateSessionRequest(
                purpose="onboarding",
                nonce="synthetic_face_nonce_1234",
                device_public_key_spki=spki(key),
            ),
        )
        session = state.sessions.get(created.session_id)
        session.purpose = "reauth"
        accounts = AccountStore(original, state.db)
        auth = AccountAuth(accounts)
        auth.bind(session, receipt.account_id, receipt.device_id)
        auth.verify(session, signed(key, message(session)))
        files = {
            "video": ("synthetic.mp4", b"synthetic-video"),
            "image": ("synthetic.jpg", b"synthetic-face"),
        }
        payload, _, _ = manifest(session, "face", files)
        verify_and_consume(state.db, session, "face", signed(key, payload), files, required=True)
        session.created_model_mode = "manual_full_demo" if original.manual_full_demo else "real"
        session.completed = True
        session.voice_challenge_id = None
        session.accepted_steps = ["media", "signals", "finalize"]
        session.results = {
            m: verdict(m)
            for m in (
                Module.QUALITY,
                Module.CAMPROBE,
                Module.CHROMAPULSE,
                Module.FACE_PAD,
                Module.FACE_DEEPFAKE,
            )
        }
        session.results[Module.FACE_MATCH] = verdict(
            Module.FACE_MATCH,
            REAUTH_MATCH_VERSION,
            quality={"enrolled_reference": True},
            evidence=[Evidence(type="text", name="reference_account_id", value=receipt.account_id)],
        )
        if original.manual_full_demo:
            policy = original.manual_demo_policy
            for module in (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH):
                result = session.results[module]
                result.model_version += policy.version_suffix
                result.quality.update(manual_demo=True, demo_policy_id=policy.policy_id)
        state.sessions.record_decision(
            session, "pass", thresholds={}, config_version="synthetic-test"
        )
        sid, token = session.session_id, session.token
    root.settings = original
    return sid, {"Authorization": "Bearer " + token}


def test_face_exchange_requires_completed_account_bound_face_and_is_one_time(enrolled):
    client = enrolled[0]
    setup(enrolled)
    sid, headers = face_session(enrolled)
    path = f"/v1/sessions/{sid}/account-access/face"
    response = client.post(path, headers=headers, json={})
    assert response.status_code == 200, response.text
    assert response.json()["authentication_method"] == "face"
    assert client.get("/v1/account-access/me", headers=access_header(response)).status_code == 200
    assert client.post(path, headers=headers, json={}).status_code == 409


@pytest.mark.parametrize(
    "fault",
    [
        "device_only",
        "missing_device_claim",
        "partial_media",
        "different_reference",
        "degraded",
        "owed_voice",
    ],
)
def test_face_exchange_fail_closed_even_if_saved_status_says_pass(enrolled, fault):
    client = enrolled[0]
    setup(enrolled)
    sid, headers = face_session(enrolled)
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        if fault == "device_only":
            session.results = {}
        elif fault == "missing_device_claim":
            state.db.delete(state.db.get(DeviceProofUseRow, sid))
        elif fault == "partial_media":
            session.accepted_steps = ["media"]
        elif fault == "different_reference":
            session.results[Module.FACE_MATCH].evidence = []
        elif fault == "degraded":
            session.results[Module.FACE_PAD] = verdict(
                Module.FACE_PAD, status="degraded", error_code="E_INTERNAL"
            )
        else:
            session.voice_owed = True
    response = client.post(f"/v1/sessions/{sid}/account-access/face", headers=headers, json={})
    assert response.status_code in {401, 409}, response.text


def test_new_enrolled_user_can_setup_after_face_but_existing_cannot_overwrite(enrolled):
    client = enrolled[0]
    sid, headers = face_session(enrolled)
    path = f"/v1/sessions/{sid}/account-access"
    response = client.post(path + "/face", headers=headers, json={})
    assert response.status_code == 409
    assert response.json()["error_code"] == "account_setup_required"
    assert client.post(path + "/setup", headers=headers, json=SETUP).status_code == 200
    second_sid, second_headers = face_session(enrolled)
    response = client.post(
        f"/v1/sessions/{second_sid}/account-access/setup", headers=second_headers, json=SETUP
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "account_already_configured"


def test_body_limits_and_validation_do_not_echo_password(enrolled):
    client, _, sid, headers, _ = enrolled
    path = f"/v1/sessions/{sid}/account-access/setup"
    assert client.post(path, json=SETUP).status_code == 401
    response = client.post(path, headers=headers, json={**SETUP, "profile_consent": False})
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert (
        client.post(path, headers=headers, json={**SETUP, "profile_consent": 1}).status_code == 422
    )
    response = client.post(
        "/v1/account-access/password", json={"username": "synthetic.user", "password": "x" * 5000}
    )
    assert response.status_code == 413


def test_token_expiry_and_disabled_feature_are_checked_on_every_request(enrolled):
    client = enrolled[0]
    setup(enrolled)
    auth = access_header(login(client))
    with client.app.state.vericlue.transaction() as state:
        state.db.scalar(select(AccountAccessTokenRow)).expires_at = utcnow() - timedelta(seconds=1)
    assert client.get("/v1/account-access/me", headers=auth).status_code == 401
    auth = access_header(login(client))
    root = client.app.state.vericlue
    root.settings = root.settings.model_copy(update={"account_access_enabled": False})
    assert client.get("/v1/account-access/me", headers=auth).status_code == 503
    assert login(client).status_code == 503


def test_recovery_can_replace_password_without_extending_account_or_leaking_old_access(enrolled):
    client, receipt, _, _, _ = enrolled
    profile = setup(enrolled)
    old_auth = access_header(login(client))
    root = client.app.state.vericlue
    original = root.settings
    root.settings = original.model_copy(
        update={"use_mock_models": True, "account_enrollment": False}
    )
    with root.transaction() as state:
        session = recovery_ready(state, receipt, new_key())
        AccountStore(original, state.db).recover(session)
        session.created_model_mode = "real"
        sid, headers = session.session_id, {"Authorization": "Bearer " + session.token}
    root.settings = original
    assert client.get("/v1/account-access/me", headers=old_auth).status_code == 401
    assert login(client).status_code == 401
    new_password = "Synthetic-replacement-2026"
    response = client.post(
        f"/v1/sessions/{sid}/account-access/setup",
        headers=headers,
        json={**SETUP, "password": new_password},
    )
    assert response.status_code == 200, response.text
    assert response.json() == profile
    assert login(client).status_code == 401
    assert login(client, password=new_password).status_code == 200
    assert client.get("/v1/account-access/me", headers=old_auth).status_code == 401


def test_username_uniqueness_and_per_peer_attempt_limit(enrolled):
    client = enrolled[0]
    setup(enrolled)
    root = client.app.state.vericlue
    original = root.settings
    root.settings = original.model_copy(
        update={"use_mock_models": True, "account_enrollment": False}
    )
    with root.transaction() as state:
        session, template, continuity = prepared(state, id_hmac="f" * 64)
        AccountStore(original, state.db).create(session, template, continuity=continuity)
        session.created_model_mode = "real"
        sid, headers = session.session_id, {"Authorization": "Bearer " + session.token}
    root.settings = original
    response = client.post(f"/v1/sessions/{sid}/account-access/setup", headers=headers, json=SETUP)
    assert response.status_code == 409
    assert response.json()["error_code"] == "username_unavailable"
    for i in range(20):
        assert login(client, username=f"missing{i:02d}").status_code == 401
    response = login(client)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "300"


def test_manual_full_account_access_keeps_policy_binding(private_client):
    root = private_client.app.state.vericlue
    key = new_key()
    with root.transaction() as state:
        with patch("test_accounts.ec.generate_private_key", return_value=key):
            session, template, _ = prepared(state, voiced=False)
        settings = real_settings(state).model_copy(
            update={
                "product_mode": "ekyc",
                "manual_full_demo": True,
                "use_mock_models": True,
                "account_enrollment": True,
                "account_access_enabled": True,
            }
        )
        policy = settings.manual_demo_policy
        session.created_model_mode = "manual_full_demo"
        session.manual_demo_policy_id = policy.policy_id
        session.created_voice_content_version = settings.voice_content_model_version
        for module in (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH):
            result = session.results[module]
            result.model_version += policy.version_suffix
            result.quality.update(manual_demo=True, demo_policy_id=policy.policy_id)
        receipt = AccountStore(settings, state.db).create(session, template)
        fixture = (
            private_client,
            receipt,
            session.session_id,
            {"Authorization": "Bearer " + session.token},
            key,
        )
    root.settings = settings
    profile = setup(fixture)
    assert profile["evaluation_mode"] == "manual_full_demo"
    assert profile["demo_policy_id"] == policy.policy_id
    response = login(private_client)
    assert response.status_code == 200, response.text
    auth = access_header(response)
    sid, headers = face_session(fixture)
    response = private_client.post(
        f"/v1/sessions/{sid}/account-access/face", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    root.settings = settings.model_copy(update={"manual_demo_pad_max": 0.321})
    assert private_client.get("/v1/account-access/me", headers=auth).status_code == 401
    assert login(private_client).status_code == 401
