import io

import app as api
import numpy as np
import pytest
from fastapi.testclient import TestClient
from identity_lab import IdentityLab, InputError, cosine, decode_image, field_candidates
from PIL import Image


def png():
    stream = io.BytesIO()
    Image.new("RGB", (30, 20), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_invalid_image_rejected():
    with pytest.raises(InputError, match="E_DECODE"):
        decode_image(b"not an image")


def test_oversized_dimensions_rejected(monkeypatch):
    monkeypatch.setattr("identity_lab.MAX_PIXELS", 100)
    with pytest.raises(InputError, match="E_IMAGE_SIZE"):
        decode_image(png())


def test_cosine_zero_norm_rejected():
    with pytest.raises(RuntimeError):
        cosine(np.zeros(5), np.ones(5))
    assert cosine(np.array([1, 0]), np.array([0, 1])) == 0


def test_candidates_do_not_extract_substrings_of_longer_ids():
    assert field_candidates([{"text": "1234567890123"}])["id_number_candidates"] == []


@pytest.mark.parametrize("faces,code", [([], "E_NO_FACE_SELFIE"), ([1, 2], "E_MULTI_FACE_SELFIE")])
def test_ambiguous_face_rejected(faces, code):
    class Detector:
        def detect(self, image):
            return faces

    lab = IdentityLab()
    lab._detector = Detector()
    with pytest.raises(InputError, match=code):
        lab._face(np.zeros((20, 20, 3)), "SELFIE")


def test_api_invalid_input():
    response = TestClient(api.app).post(
        "/dev/v1/ocr", files={"image": ("bad.png", b"bad", "image/png")}
    )
    assert response.status_code == 422


def test_api_model_failure_never_passes(monkeypatch):
    def broken(data):
        raise RuntimeError("private internal path")

    monkeypatch.setattr(api.lab, "ocr", broken)
    response = TestClient(api.app).post(
        "/dev/v1/ocr", files={"image": ("test.png", png(), "image/png")}
    )
    assert response.status_code == 503
    assert "private" not in response.text


def test_api_upload_size(monkeypatch):
    monkeypatch.setattr(api, "MAX_BYTES", 3)
    response = TestClient(api.app).post(
        "/dev/v1/ocr", files={"image": ("test.png", png(), "image/png")}
    )
    assert response.status_code == 413
