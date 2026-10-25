import io
from types import SimpleNamespace

import app as api
import numpy as np
import pytest
from evaluate_faces import summarize
from face_matching import match_pair, validate_face
from fastapi.testclient import TestClient
from identity_lab import IdentityLab, InputError
from PIL import Image
from prepare_lfw import parse_pairs
from schemas import FacePairResult


def image_bytes(format="PNG"):
    stream = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(stream, format=format)
    return stream.getvalue()


def test_identical_pixels_rejected_before_models_even_different_encoding():
    lab = IdentityLab()
    result = match_pair(lab, image_bytes(), image_bytes("WEBP"))
    assert result["reason"] == "E_IDENTICAL_INPUTS"
    assert result["cosine_similarity"] is None
    assert lab._detector is None
    FacePairResult.model_validate(result)


def test_geometry_rejects_small_or_clipped_faces():
    face = SimpleNamespace(bbox=[10, 10, 20, 20], landmarks=np.ones((5, 2)), confidence=0.9)
    with pytest.raises(InputError, match="TOO_SMALL"):
        validate_face(face, np.zeros((100, 100, 3), dtype=np.uint8), "SELFIE")
    face.bbox = [-2, 0, 80, 80]
    with pytest.raises(InputError, match="CLIPPED"):
        validate_face(face, np.zeros((100, 100, 3), dtype=np.uint8), "SELFIE")


def test_lfw_pairs_labels_and_path_validation():
    rows = parse_pairs("2\nPerson_A 1 2\nPerson_A 1 Person_B 1")
    assert rows[0]["same_person"] and not rows[1]["same_person"]
    assert rows[0]["reference"] == "lfw/Person_A/Person_A_0001.jpg"
    with pytest.raises(ValueError):
        parse_pairs("../bad 1 2")


def test_auc_and_failures_are_separate():
    records = [
        {"status": "ok", "same_person": True, "cosine_similarity": 0.8},
        {"status": "ok", "same_person": False, "cosine_similarity": 0.1},
        {"status": "retry", "same_person": True, "reason": "NO_FACE"},
    ]
    result = summarize(records)
    assert result["roc_auc_scored_pairs_only"] == 1
    assert result["unscored_pairs"] == 1 and result["same_person_total"] == 2
    assert result["threshold"] is None
    assert (
        summarize([{"status": "retry", "same_person": False, "reason": "NO_FACE"}])[
            "roc_auc_scored_pairs_only"
        ]
        is None
    )


def test_v2_api_duplicate_and_bad_file():
    client = TestClient(api.app)
    same = image_bytes()
    result = client.post(
        "/dev/v2/face-match",
        files={"reference": ("a.png", same, "image/png"), "selfie": ("b.png", same, "image/png")},
    )
    assert result.status_code == 200
    assert result.json()["decision"] == "retry"
    result = client.post(
        "/dev/v2/face-match",
        files={"reference": ("a.png", b"bad", "image/png"), "selfie": ("b.png", same, "image/png")},
    )
    assert result.status_code == 422


def test_v2_model_failure_not_a_match(monkeypatch):
    def broken(*args):
        raise RuntimeError("internal secret path")

    monkeypatch.setattr(api, "match_pair", broken)
    response = TestClient(api.app).post(
        "/dev/v2/face-match",
        files={
            "reference": ("a.png", image_bytes(), "image/png"),
            "selfie": ("b.png", image_bytes(), "image/png"),
        },
    )
    assert response.status_code == 503
    assert "secret" not in response.text
