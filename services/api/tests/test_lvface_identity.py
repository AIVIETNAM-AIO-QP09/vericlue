"""Local LVFace identity integration with synthetic pixels/embeddings, not accuracy data."""

import json
from pathlib import Path

import numpy as np
import pytest
from conftest import start_session
from fastapi.testclient import TestClient

from vericlue_api.core.config import get_settings
from vericlue_api.main import create_app
from vericlue_api.services import orchestrator as orchestration
from vericlue_api.services.identity_runtime import IdentityRuntime
from vericlue_ml.common.result import Gate, Module, Status
from vericlue_ml.face.match import ALIGNMENT_ID, ARCFACE_TARGET, MATCH_VERSION, FaceMatchDetector
from vericlue_ml.face.pad import FaceBox

QR = "001099012345||Test Person|01011995|Nam|Synthetic Address|15062021"


def png(level):
    cv2 = pytest.importorskip("cv2")
    ok, data = cv2.imencode(".png", np.full((140, 140, 3), level, dtype=np.uint8))
    assert ok
    return data.tobytes()


@pytest.fixture
def identity_app(monkeypatch, tmp_path, request):
    options = getattr(request, "param", {})
    instances = []
    mode = options.get("calibration")
    monkeypatch.delenv("FACE_MATCH_CALIBRATION", raising=False)
    monkeypatch.setenv("IDENTITY_CARD_ENABLED", "true")
    # The old AdaFace variable must never become an implicit LVFace threshold.
    monkeypatch.setenv("IDENTITY_FACE_THRESHOLD", "0.40")
    if mode:
        path = tmp_path / "synthetic-threshold.json"
        path.write_text(
            json.dumps(
                {
                    "model_version": MATCH_VERSION
                    if mode == "valid"
                    else "adaface-ir18-context@identity-lab-v1",
                    "preprocessing": ALIGNMENT_ID,
                    "threshold": 0.6,
                    "split": "calib_ltt",
                    "dataset": "synthetic_unit_test_not_calibration",
                    "pairs": 4,
                    "subjects": 2,
                    "source_commit": "a" * 40,
                    "predictions_sha256": "b" * 64,
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("IDENTITY_FACE_CALIBRATION", str(path))
    else:
        monkeypatch.delenv("IDENTITY_FACE_CALIBRATION", raising=False)

    class Finder:
        def find(self, image):
            return [FaceBox(5, 5, 105, 105, 0.99, ARCFACE_TARGET)]

    class Embedder:
        def embed(self, tensor):
            result = np.zeros(512, dtype=np.float32)
            different = options.get("mismatch") and float(tensor.mean()) > -0.5
            result[int(bool(different))] = 1
            return result

    class SyntheticLVFace(FaceMatchDetector):
        def __init__(self, **kwargs):
            super().__init__(finder=Finder(), embedder=Embedder(), **kwargs)
            self.loads = 0
            self.inputs = []
            self.preload_options = None
            instances.append(self)

        def preload(self, **kwargs):
            if not self._loaded:
                self.loads += 1
                self.preload_options = kwargs
            return super().preload(**kwargs)

        def predict(self, inp):
            self.inputs.append(inp.model_copy(deep=True))
            return super().predict(inp)

    def local_scan(self, front, back):
        assert front and back
        return {"qr_values": [QR], "fields": {}}

    monkeypatch.setattr(orchestration, "FaceMatchDetector", SyntheticLVFace)
    monkeypatch.setattr(IdentityRuntime, "scan", local_scan)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client, instances


def verify(client):
    created, auth = start_session(client)
    sid = created["session_id"]
    endpoint = f"/v1/sessions/{sid}"
    card = client.post(
        endpoint + "/id-card",
        headers=auth,
        files={
            "front": ("front.png", png(30), "image/png"),
            "back": ("back.png", png(40), "image/png"),
        },
    )
    assert card.status_code == 200
    assert (
        client.post(
            endpoint + "/id-card/confirm", headers=auth, json=card.json()["fields"]
        ).status_code
        == 200
    )
    assert (
        client.post(
            endpoint + "/media",
            headers=auth,
            files={
                "image": ("front.png", png(100), "image/png"),
            },
        ).status_code
        == 200
    )
    response = client.post(endpoint + "/finalize", headers=auth)
    assert response.status_code == 200
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(sid)
        return response, session.results[Module.FACE_MATCH], session.id_front, session.images[0]


@pytest.mark.parametrize(
    "identity_app,expected,model_status",
    [
        ({}, "review", Status.DEGRADED),
        ({"calibration": "valid"}, "pass", Status.OK),
        ({"calibration": "valid", "mismatch": True}, "review", Status.OK),
        ({"calibration": "adaface"}, "review", Status.ERROR),
    ],
    indirect=["identity_app"],
)
def test_card_selfie_uses_local_lvface_and_only_its_own_calibration(
    identity_app, expected, model_status
):
    client, instances = identity_app
    response, result, reference, front = verify(client)
    assert response.json()["status"] == expected
    assert result.status == model_status
    assert result.prob_attack is None
    for forbidden in ("score", "cosine", "lvface", "threshold", "evidence"):
        assert forbidden not in response.text
    if model_status != Status.ERROR:
        assert result.model_version == MATCH_VERSION
        assert result.quality["comparisons"] == 1
        assert result.quality["consistency_comparisons"] == 0
        if expected == "review":
            assert result.gate != Gate.PASS
        inp = instances[0].inputs[0]
        assert inp.reference_image == reference
        assert inp.images == [front] and inp.image_roles == ["front"]
        assert instances[0].preload_options == {
            "models_dir": Path(client.app.state.vericlue.settings.models_dir),
            "device": client.app.state.vericlue.settings.device,
        }
    else:
        assert not instances[0].inputs
        assert "face_match" in client.get("/healthz").json()["failed_modules"]


def test_lvface_is_preloaded_once_and_reused_across_sessions(identity_app):
    client, instances = identity_app
    for _ in range(2):
        response, result, *_ = verify(client)
        assert response.json()["status"] == "review"
        assert result.status == Status.DEGRADED
    assert len(instances) == 1
    assert instances[0].loads == 1 and len(instances[0].inputs) == 2
