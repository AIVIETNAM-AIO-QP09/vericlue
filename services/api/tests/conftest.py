from __future__ import annotations

import json
import secrets
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from vericlue_api.core.config import get_settings
from vericlue_api.main import create_app


@pytest.fixture(scope="session")
def db_template(tmp_path_factory):
    path = tmp_path_factory.mktemp("sqlite-template") / "template.db"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", "sqlite:///" + path.as_posix())
    command.upgrade(config, "head")
    return path


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch, tmp_path, db_template):
    path = tmp_path / "test.db"
    shutil.copyfile(db_template, path)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + path.as_posix())
    monkeypatch.setenv("FORENSIC_TTL_DAYS", "")
    monkeypatch.setenv("USE_MOCK_MODELS", "true")
    # General scenario tests create many sessions. Rate-limit tests use the real default.
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "1000")
    monkeypatch.setenv("SESSION_SIGNING_SECRET", secrets.token_urlsafe(32))
    token = secrets.token_urlsafe(32)
    monkeypatch.setenv("STAFF_ACCESS_TOKENS", json.dumps({token: "staff-test"}))
    # Ephemeral real key for report crypto tests, independent of biometric/mock verdicts.
    report_key = tmp_path / "report-signing.pem"
    report_key.write_bytes(
        Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    monkeypatch.setenv("REPORT_SIGNING_KEY_PATH", str(report_key))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    """Business tests use a configured staff credential; citizen tokens remain separate.

    Authentication tests explicitly create an anonymous TestClient instead.
    """
    with staff_test_client(create_app()) as instance:
        yield instance


def staff_test_client(app) -> TestClient:
    """Use real authentication in integration tests, never patch the guard off."""
    token = next(
        iter(json.loads(app.state.vericlue.settings.staff_access_tokens.get_secret_value()))
    )
    return TestClient(app, headers={"Authorization": "Bearer " + token})


def start_session(client: TestClient, scenario: str = "genuine") -> tuple[dict, dict]:
    """Tạo phiên mock theo kịch bản; trả (phản hồi JSON, header Bearer)."""
    res = client.post("/v1/sessions", headers={"X-Mock-Scenario": scenario})
    assert res.status_code == 200, res.text
    body = res.json()
    return body, {"Authorization": f"Bearer {body['token']}"}
