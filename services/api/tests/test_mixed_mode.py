"""USE_MOCK_MODELS=mixed: module có mô hình thật dùng thật, thiếu trọng số thì vào failed_modules."""

from __future__ import annotations

import pytest
from conftest import staff_test_client, start_session
from fastapi.testclient import TestClient
from synthetic_images import synthetic_image

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.main import create_app

IMAGE = {"image": ("face.jpg", synthetic_image(b"\xff\xd8\xff"), "image/jpeg")}
SIGNALS = {
    "color_events": [{"index": 0, "rgb": "#ffcc73", "painted_at": 1234.5}],
    "frame_times": [{"capture_time": 1240.2, "presented_frames": 31, "media_time": 0.5}],
}


def make_client(monkeypatch, tmp_path, mode: str) -> TestClient:
    models = tmp_path / "no-models"
    models.mkdir(exist_ok=True)
    monkeypatch.setenv("USE_MOCK_MODELS", mode)
    monkeypatch.setenv("MODELS_DIR", str(models))
    get_settings.cache_clear()
    return staff_test_client(create_app())


@pytest.fixture
def mixed_client(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, "mixed") as client:
        yield client


def test_settings_accepts_mixed_and_bools():
    assert Settings(use_mock_models="mixed").use_mock_models == "mixed"
    assert Settings(use_mock_models="true").use_mock_models is True
    assert Settings(use_mock_models="false").use_mock_models is False
    assert Settings(use_mock_models=True).use_mock_models is True
    assert Settings().use_mock_models is True


def test_settings_rejects_garbage():
    with pytest.raises(ValueError):
        Settings(use_mock_models="banana")


def test_settings_reads_mixed_from_env(monkeypatch):
    monkeypatch.setenv("USE_MOCK_MODELS", "mixed")
    assert Settings().use_mock_models == "mixed"


def test_app_starts_without_weights_and_reports_degraded(mixed_client):
    res = mixed_client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "degraded"
    assert "face_pad" in body["failed_modules"]
    assert body["mock_models"] is True
    assert isinstance(body["mock_models"], bool)


@pytest.mark.parametrize("mode", ["true", "false", "mixed"])
def test_healthz_mock_models_is_bool(monkeypatch, tmp_path, mode):
    with make_client(monkeypatch, tmp_path, mode) as client:
        body = client.get("/healthz").json()
    assert isinstance(body["mock_models"], bool)
    assert body["mock_models"] is (mode != "false")
    if mode == "true":
        assert body["status"] == "ok" and body["failed_modules"] == []


def test_demo_cases_seeded_in_mixed(mixed_client):
    res = mixed_client.get("/v1/review/cases")
    assert res.status_code == 200
    text = res.text
    assert "ses_demo_virtual_cam" in text and "ses_demo_print" in text


def test_demo_cases_not_seeded_when_false(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, "false") as client:
        assert "ses_demo" not in client.get("/v1/review/cases").text


def test_mock_scenario_header_accepted_in_mixed(mixed_client):
    body, _ = start_session(mixed_client, "print")
    assert body["session_id"]


def test_unknown_scenario_still_rejected_in_mixed(mixed_client):
    res = mixed_client.post("/v1/sessions", headers={"X-Mock-Scenario": "khong_co"})
    assert res.status_code == 422


def test_failed_face_pad_never_yields_pass(mixed_client):
    body, auth = start_session(mixed_client, "genuine")
    sid = body["session_id"]
    base = f"/v1/sessions/{sid}"
    assert mixed_client.post(f"{base}/media", headers=auth, files=IMAGE).status_code == 200
    assert mixed_client.post(f"{base}/signals", headers=auth, json=SIGNALS).status_code == 200
    res = mixed_client.post(f"{base}/finalize", headers=auth)
    assert res.status_code == 200
    # face_pad lỗi (không có trọng số) thì không bao giờ được 'pass'
    assert res.json() == {"status": "review"}  # hành vi quan sát được: lỗi → bàn duyệt


def test_face_pad_ok_without_calibrator_still_goes_to_review(monkeypatch, tmp_path):
    """face_pad chạy ok (p_real cao) nhưng chưa có calibrator → router không cho pass → review."""
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    from vericlue_ml import registry
    from vericlue_ml.common.result import Module
    from vericlue_ml.face.pad import FaceBox, FacePadDetector

    seen = []

    class Finder:
        def find(self, image):
            seen.append(image.shape)
            return [FaceBox(10, 10, 90, 90, 0.99)]

    class Classifier:
        def p_real(self, image, box):
            return 0.99

    detector = FacePadDetector(finder=Finder(), classifier=Classifier())
    monkeypatch.setitem(registry._REAL_FACTORIES, Module.FACE_PAD, lambda: detector)
    ok, png = cv2.imencode(".png", np.full((120, 120, 3), 127, np.uint8))
    assert ok
    with make_client(monkeypatch, tmp_path, "mixed") as client:
        body, auth = start_session(client, "genuine")
        base = f"/v1/sessions/{body['session_id']}"
        files = {"image": ("face.png", png.tobytes(), "image/png")}
        assert client.post(f"{base}/media", headers=auth, files=files).status_code == 200
        assert client.post(f"{base}/signals", headers=auth, json=SIGNALS).status_code == 200
        res = client.post(f"{base}/finalize", headers=auth)
    assert seen, "face_pad giả phải được gọi"
    assert res.status_code == 200
    assert res.json() == {"status": "review"}


def test_settings_normalizes_mixed_case():
    assert Settings(use_mock_models=" MIXED ").use_mock_models == "mixed"
    assert Settings(use_mock_models="TRUE").use_mock_models is True
