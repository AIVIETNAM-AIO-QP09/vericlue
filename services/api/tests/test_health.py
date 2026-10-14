from fastapi.testclient import TestClient

from vericlue_api.main import create_app


def test_healthz_ok():
    client = TestClient(create_app())
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert isinstance(body["mock_models"], bool)
