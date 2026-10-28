"""SEC-05 uses ephemeral independent secrets; no biometric or deployment claims."""

from __future__ import annotations

import base64
import json
import re
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.security_profile import (
    ensure_otp_available,
    security_profile_checks,
    validate_security_profile,
)


def protected(**updates) -> Settings:
    values = {
        "security_profile": "protected",
        "product_mode": "ekyc",
        "require_privacy_consent": True,
        "session_privacy": True,
        "require_media_proof": True,
        "use_mock_models": False,
        "session_master_key": base64.b64encode(secrets.token_bytes(32)).decode(),
        "id_hmac_key": secrets.token_urlsafe(32),
        "session_signing_secret": secrets.token_urlsafe(32),
    }
    values.update(updates)
    return Settings(_env_file=None, **values)


def test_valid_independent_protected_configuration_is_accepted():
    settings = protected()
    assert all(security_profile_checks(settings).values())
    validate_security_profile(settings)


@pytest.mark.parametrize(
    "changes",
    [
        {"product_mode": "tools"},
        {"require_privacy_consent": False},
        {"session_privacy": False},
        {"require_media_proof": False},
        {"session_master_key": None},
        {"session_master_key": "not-base64"},
        {"session_master_key": base64.b64encode(b"x" * 31).decode()},
        {"session_master_key": base64.b64encode(b"x" * 32).decode()},
        {"id_hmac_key": "dev-only-not-secret"},
        {"id_hmac_key": "change-me-please-do-not-use-this-secret"},
        {"id_hmac_key": "x" * 40},
        {"session_signing_secret": None},
        {"session_signing_secret": "short"},
        {"use_mock_models": True},
        {"use_mock_models": "mixed"},
    ],
)
def test_protected_profile_rejects_missing_or_unsafe_components(changes):
    with pytest.raises(ApiError) as caught:
        validate_security_profile(protected(**changes))
    assert caught.value.status_code == 503
    assert caught.value.error_code == "security_profile_unavailable"
    assert "change-me" not in caught.value.message


@pytest.mark.parametrize("pair", ["hmac-token", "master-hmac", "master-token"])
def test_protected_secrets_cannot_reuse_material(pair):
    settings = protected()
    if pair == "hmac-token":
        settings.session_signing_secret = settings.id_hmac_key
    elif pair == "master-hmac":
        settings.id_hmac_key = settings.session_master_key
    else:
        raw = secrets.token_urlsafe(24).encode()
        assert len(raw) == 32
        settings.session_master_key = SecretStr(base64.b64encode(raw).decode())
        settings.session_signing_secret = SecretStr(raw.decode())
    assert security_profile_checks(settings)["independent_secrets"] is False
    with pytest.raises(ApiError):
        validate_security_profile(settings)


def test_protected_failure_precedes_application_state_creation(monkeypatch):
    import vericlue_api.main as api

    monkeypatch.setattr(api, "get_settings", lambda: protected(session_privacy=False))

    def forbidden(**kwargs):
        pytest.fail("DB/model state must not be constructed for unsafe protected config")

    monkeypatch.setattr(api, "ApplicationState", forbidden)
    with pytest.raises(ApiError) as caught:
        api.create_app()
    assert caught.value.error_code == "security_profile_unavailable"


def test_synthetic_labs_remain_explicitly_synthetic():
    settings = Settings(_env_file=None, security_profile="synthetic", use_mock_models=True)
    validate_security_profile(settings)
    ensure_otp_available(settings)


@pytest.mark.parametrize("mode", [False, "mixed", True])
def test_simulated_sms_unavailable_in_protected_profile(mode):
    with pytest.raises(ApiError) as caught:
        ensure_otp_available(protected(use_mock_models=mode))
    assert caught.value.error_code == "otp_unavailable"


@pytest.mark.parametrize("mode", [False, "mixed"])
def test_simulated_sms_cannot_be_used_in_real_or_mixed_labs(mode):
    with pytest.raises(ApiError) as caught:
        ensure_otp_available(Settings(_env_file=None, use_mock_models=mode))
    assert caught.value.error_code == "otp_unavailable"


@pytest.mark.parametrize(
    "mode,profile", [(False, "synthetic"), ("mixed", "synthetic"), (True, "protected")]
)
def test_existing_simulated_otp_cannot_be_verified_after_mode_switch(client, mode, profile):
    from conftest import start_session

    session, auth = start_session(client)
    sid = session["session_id"]
    sent = client.post(f"/v1/sessions/{sid}/otp", headers=auth, json={"phone": "0900000000"})
    assert sent.status_code == 200
    code = re.search(r"\b(\d{6})\b", sent.json()["simulated_sms"]).group(1)
    root = client.app.state.vericlue
    root.settings = root.settings.model_copy(
        update={"use_mock_models": mode, "security_profile": profile}
    )
    denied = client.post(f"/v1/sessions/{sid}/otp/verify", headers=auth, json={"code": code})
    assert denied.status_code == 503 and denied.json()["error_code"] == "otp_unavailable"
    assert "simulated_sms" not in denied.text and "pass" not in denied.text
    with root.transaction() as state:
        stored = state.sessions.get(sid)
        assert stored.otp_verified is False
        assert stored.otp_attempts_left == 5


@pytest.mark.parametrize("mode", [False, "mixed"])
def test_real_mode_legacy_otp_never_returns_a_simulated_sms(client, mode):
    from conftest import start_session

    root = client.app.state.vericlue
    root.settings = root.settings.model_copy(update={"use_mock_models": mode})
    session, auth = start_session(client)
    sid = session["session_id"]
    denied = client.post(f"/v1/sessions/{sid}/otp", headers=auth, json={"phone": "0900000000"})
    assert denied.status_code == 503 and denied.json()["error_code"] == "otp_unavailable"
    assert "simulated_sms" not in denied.text
    with root.transaction() as state:
        stored = state.sessions.get(sid)
        assert stored.otp_hash is None and stored.phone_hmac is None and stored.otp_sends == 0


def test_preflight_outputs_metadata_without_secrets_or_db_access(tmp_path, monkeypatch):
    root = Path(__file__).parents[3]
    settings = protected()
    monkeypatch.setenv("SECURITY_PROFILE", "protected")
    monkeypatch.setenv("PRODUCT_MODE", "ekyc")
    monkeypatch.setenv("REQUIRE_PRIVACY_CONSENT", "true")
    monkeypatch.setenv("SESSION_PRIVACY", "true")
    monkeypatch.setenv("REQUIRE_MEDIA_PROOF", "true")
    monkeypatch.setenv("USE_MOCK_MODELS", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://not-a-real-host/profile")
    for field, name in [
        ("session_master_key", "SESSION_MASTER_KEY"),
        ("id_hmac_key", "ID_HMAC_KEY"),
        ("session_signing_secret", "SESSION_SIGNING_SECRET"),
    ]:
        monkeypatch.setenv(name, getattr(settings, field).get_secret_value())
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_security_profile.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["protected_configuration_ok"] is True
    assert "biometric_acceptance" in output["not_checked"]
    for field in ("session_master_key", "id_hmac_key", "session_signing_secret"):
        secret = getattr(settings, field).get_secret_value()
        assert secret not in result.stdout + result.stderr
    assert "not-a-real-host" not in result.stdout + result.stderr


@pytest.mark.parametrize("failure", ["master", "profile"])
def test_preflight_invalid_config_exits_nonzero_without_values(tmp_path, monkeypatch, failure):
    root = Path(__file__).parents[3]
    monkeypatch.setenv("SECURITY_PROFILE", "protected")
    monkeypatch.setenv("SESSION_MASTER_KEY", "sensitive-invalid-value")
    if failure == "profile":
        monkeypatch.setenv("SECURITY_PROFILE", "sensitive-invalid-profile")
    result = subprocess.run(
        [sys.executable, str(root / "scripts/check_security_profile.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["protected_configuration_ok"] is False
    assert "sensitive-invalid-value" not in result.stdout + result.stderr
    assert "sensitive-invalid-profile" not in result.stdout + result.stderr
