from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vericlue_api.core.config import get_settings
from vericlue_api.main import create_app


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_MOCK_MODELS", "true")
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    """Mỗi test có một ứng dụng (và kho dữ liệu trong bộ nhớ) riêng."""
    return TestClient(create_app())


def start_session(client: TestClient, scenario: str = "genuine") -> tuple[dict, dict]:
    """Tạo phiên mock theo kịch bản; trả (phản hồi JSON, header Bearer)."""
    res = client.post("/v1/sessions", headers={"X-Mock-Scenario": scenario})
    assert res.status_code == 200, res.text
    body = res.json()
    return body, {"Authorization": f"Bearer {body['token']}"}
