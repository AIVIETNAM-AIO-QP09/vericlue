import hashlib
import io
import threading
from types import SimpleNamespace

import app as api
import numpy as np
import pytest
from calibrate_faces import ensure_disjoint, fit, metrics, validate_records
from face_matching import face_embedding, match_pair, reference_crop, validate_face
from fastapi.testclient import TestClient
from identity_lab import InputError
from PIL import Image
from schemas import FacePairResult
from serve_face_lab import select_config


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def record(index, same, score, status="ok"):
    return {
        "reference_identity": f"p{index}",
        "selfie_identity": f"p{index}" if same else f"q{index}",
        "reference_pixel_sha256": digest(f"a{index}"),
        "selfie_pixel_sha256": digest(f"b{index}"),
        "same_person": same,
        "status": status,
        "cosine_similarity": score,
        "reason": "E_NO_FACE_IMAGE" if status == "retry" else None,
    }


def test_calibration_ties_and_retries():
    rows = [
        record(0, True, 0.8),
        record(1, False, 0.3),
        record(2, False, 0.3),
        record(3, True, None, "retry"),
    ]
    result = fit(rows, 0.5)
    assert result["threshold"] > 0.3 and result["false_matches"] == 0
    assert result["fnmr_scored"] == 0 and result["genuine_not_matched_including_retry_rate"] == 0.5
    assert metrics(rows, 0.3)["false_matches"] == 2  # >= boundary is deliberate.


def test_calibration_rejects_leakage_bad_labels_and_scores():
    rows = [record(0, True, 0.8), record(1, False, 0.3)]
    ids, hashes = validate_records(rows)
    with pytest.raises(ValueError, match="identity overlap"):
        ensure_disjoint(rows, {"calibration_identities": list(ids), "calibration_pixels": []})
    with pytest.raises(ValueError, match="image overlap"):
        ensure_disjoint(rows, {"calibration_identities": [], "calibration_pixels": list(hashes)})
    with pytest.raises(ValueError, match="Duplicate"):
        validate_records(rows + rows)
    with pytest.raises(ValueError, match="label"):
        validate_records([{**rows[0], "same_person": False}])
    with pytest.raises(ValueError, match="Invalid scored"):
        validate_records([{**rows[0], "cosine_similarity": float("nan")}])


def test_calibration_rejects_image_with_conflicting_identity():
    first, second = record(0, True, 0.8), record(1, True, 0.7)
    second["reference_pixel_sha256"] = first["reference_pixel_sha256"]
    with pytest.raises(ValueError, match="conflicting identities"):
        validate_records([first, second])


def test_select_one_fixed_model_and_reject_incomparable_runs():
    def candidate(model, auc):
        return {
            "total_pairs": 100,
            "scored_pairs": 90,
            "pair_manifest_sha256": "same",
            "roc_auc_scored_pairs_only": auc,
            "recognition_latency_ms": {"median": 50 if model == "adaface_ir18" else 500},
            "pipeline": {"recognizer": model, "embedding_mode": "single"},
        }

    report = {
        "configs": {"ada": candidate("adaface_ir18", 0.98), "arc": candidate("arcface_r50", 0.99)}
    }
    name, config = select_config(report)
    assert name == "arc" and config["recognizer"] == "arcface_r50"
    report["configs"]["ada"]["roc_auc_scored_pairs_only"] = 0.9895
    assert select_config(report)[0] == "ada"
    assert select_config(report, auc_tolerance=0)[0] == "arc"
    with pytest.raises(ValueError, match="tolerance"):
        select_config(report, auc_tolerance=float("nan"))
    report["configs"]["arc"]["scored_pairs"] = 89
    with pytest.raises(ValueError, match="different pairs"):
        select_config(report)


def test_calibration_cli_fit_then_disjoint_evaluation(tmp_path, monkeypatch):
    import json
    import sys

    import calibrate_faces

    for split, offset in (("calibration", 0), ("test", 10)):
        directory = tmp_path / split
        directory.mkdir()
        (directory / "pairs.json").write_text(
            json.dumps([record(offset, True, 0.8), record(offset + 1, False, 0.3)])
        )
        (directory / "summary.json").write_text(json.dumps({"pipeline": {"test_only": True}}))
    artifact = tmp_path / "threshold.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "calibrate_faces.py",
            "fit",
            "--run",
            str(tmp_path / "calibration"),
            "--out",
            str(artifact),
            "--target-fmr",
            "0",
        ],
    )
    calibrate_faces.main()
    result = tmp_path / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "calibrate_faces.py",
            "evaluate",
            "--run",
            str(tmp_path / "test"),
            "--out",
            str(result),
            "--calibration",
            str(artifact),
        ],
    )
    calibrate_faces.main()
    report = json.loads(result.read_text())
    assert report["identity_and_pixel_disjoint"] is True
    assert report["metrics"]["false_matches"] == 0 and report["production_ready"] is False


@pytest.mark.parametrize(
    "roi", [[0, 0, 101, 100], [0, 0, 10, 10], [0.0, 0, 50, 50], [True, 0, 50, 50], "0,0,50,50"]
)
def test_roi_validation(roi):
    with pytest.raises(InputError, match="REFERENCE_ROI"):
        reference_crop(np.zeros((100, 100, 3), dtype=np.uint8), roi)


def test_landmarks_reject_degenerate_layout():
    face = SimpleNamespace(
        bbox=[0, 0, 90, 90],
        confidence=0.9,
        landmarks=np.array([[10, 10], [25, 25], [40, 40], [55, 55], [70, 70]]),
    )
    with pytest.raises(InputError, match="LANDMARKS"):
        validate_face(face, np.zeros((100, 100, 3), dtype=np.uint8), "SELFIE")


def test_flip_normalizes_views_before_averaging_and_rejects_invalid():
    vectors = iter([np.array([3.0, 0.0]), np.array([0.0, 8.0])])
    model = SimpleNamespace(get_embedding=lambda _: next(vectors))
    result = face_embedding(model, np.zeros((112, 112, 3)), "flip_mean")
    np.testing.assert_allclose(result, [2**-0.5, 2**-0.5])
    for vector in ([0.0, 0.0], [float("inf"), 1], []):
        with pytest.raises(RuntimeError, match="Invalid embedding"):
            face_embedding(
                SimpleNamespace(get_embedding=lambda _, v=vector: v), np.zeros((112, 112, 3))
            )


def png(array):
    output = io.BytesIO()
    Image.fromarray(array).save(output, format="PNG")
    return output.getvalue()


def test_roi_coordinates_and_api(monkeypatch):
    import face_matching

    def fake_extract(lab, image, role, *args):
        return np.array([1.0, 0.0]), {
            "bbox": [1, 2, 35, 40],
            "landmarks": [[10, 10]] * 5,
            "detection_score": 0.9,
            "quality": {},
            "warnings": [],
        }

    monkeypatch.setattr(face_matching, "extract_face", fake_extract)
    lab = SimpleNamespace(
        face_model="arcface_r50", _lock=threading.RLock(), _load_faces=lambda: None
    )
    first = png(np.zeros((100, 100, 3), dtype=np.uint8))
    second = png(np.full((100, 100, 3), 255, dtype=np.uint8))
    result = match_pair(lab, first, second, reference_roi=[20, 30, 90, 100])
    assert result["reference"]["bbox"] == [21, 32, 55, 70]
    assert result["reference"]["landmarks"][0] == [30, 40]
    assert result["selfie"]["bbox"] == [1, 2, 35, 40]
    FacePairResult.model_validate(result)
    monkeypatch.setattr(api, "lab", lab)
    client = TestClient(api.app)
    for roi in ("broken", "[0,0,999,999]"):
        response = client.post(
            "/dev/v2/face-match",
            files={"reference": ("r.png", first), "selfie": ("s.png", second)},
            data={"reference_roi": roi},
        )
        assert response.status_code == 422
    response = client.post(
        "/dev/v2/face-match",
        files={"reference": ("r.png", first), "selfie": ("s.png", second)},
        data={"reference_roi": "[20,30,90,100]", "embedding_mode": "flip_mean"},
    )
    assert response.status_code == 200 and response.json()["model"] == "SCRFD-10G+ArcFace-R50"
    assert response.json()["identity_verified"] is False
