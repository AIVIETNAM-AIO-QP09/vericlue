"""Deterministic identity comparisons with synthetic pixels/embeddings, no biometric fixtures."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Gate, Status
from vericlue_ml.face.match import (
    ALIGNMENT_ID,
    ARCFACE_TARGET,
    MATCH_VERSION,
    FaceMatchDetector,
    LVFaceEmbedder,
    MatchError,
    match_tensor,
    normalized,
    similarity_transform,
)
from vericlue_ml.face.pad import FaceBox


def test_alignment_recovers_known_rotation_scale_translation():
    angle = 0.2
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    source = ARCFACE_TARGET @ rotation.T * 1.7 + [20, 30]
    matrix = similarity_transform(source)
    transformed = np.column_stack([source, np.ones(5)]) @ matrix.T
    np.testing.assert_allclose(transformed, ARCFACE_TARGET, atol=1e-5)
    assert np.linalg.det(matrix[:, :2]) > 0


@pytest.mark.parametrize("points", [np.zeros((5, 2)), np.zeros((4, 2)), np.full((5, 2), np.nan)])
def test_degenerate_alignment_is_rejected(points):
    with pytest.raises(MatchError):
        similarity_transform(points)


def test_preprocessing_is_rgb_float32_chw_minus_one_to_one():
    bgr = np.full((112, 112, 3), [0, 127, 255], dtype=np.uint8)
    tensor = match_tensor(bgr)
    assert tensor.shape == (1, 3, 112, 112) and tensor.dtype == np.float32
    np.testing.assert_allclose(tensor[0, :, 50, 50], [1, 127 / 127.5 - 1, -1], atol=1e-7)
    assert tensor.flags.c_contiguous


@pytest.mark.parametrize("vector", [np.zeros(512), np.ones(128), np.full(512, np.nan)])
def test_invalid_model_output_is_rejected(vector):
    with pytest.raises(MatchError):
        normalized(vector)


def vector(index=0):
    value = np.zeros(512, dtype=np.float32)
    value[index] = 1
    return value


def artifact(tmp_path, **changes):
    payload = dict(
        model_version=MATCH_VERSION,
        preprocessing=ALIGNMENT_ID,
        threshold=0.6,
        split="calib_ltt",
        dataset="synthetic_unit_test_not_calibration",
        pairs=4,
        subjects=2,
        source_commit="a" * 40,
        predictions_sha256="b" * 64,
    )
    payload.update(changes)
    path = tmp_path / "synthetic-threshold.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def setup_detector(tmp_path, *, vectors=None, threshold=False, faces=None):
    cv2 = pytest.importorskip("cv2")
    paths = []
    for i in range(4):
        path = tmp_path / f"synthetic-{i}.png"
        assert cv2.imwrite(str(path), np.full((112, 112, 3), 40 + i * 25, dtype=np.uint8))
        paths.append(path)

    class Finder:
        def find(self, image):
            return faces if faces is not None else [FaceBox(5, 5, 105, 105, 0.99, ARCFACE_TARGET)]

    class Embedder:
        def __init__(self):
            self.values = iter(vectors if vectors is not None else [vector()] * 4)

        def embed(self, tensor):
            assert tensor.shape == (1, 3, 112, 112)
            return next(self.values)

    detector = FaceMatchDetector(
        finder=Finder(),
        embedder=Embedder(),
        calibration_path=artifact(tmp_path) if threshold else None,
    )
    inp = DetectorInput(
        reference_image=paths[0], images=paths[1:], image_roles=["front", "left", "right"]
    )
    return detector, inp


def test_no_threshold_stays_degraded_even_for_identical_embeddings(tmp_path, monkeypatch):
    monkeypatch.delenv("FACE_MATCH_CALIBRATION", raising=False)
    detector, inp = setup_detector(tmp_path)
    inp.signals = {"face_match": {"gate": "pass", "threshold": -1}}
    result = detector.predict(inp)
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR
    assert result.prob_attack is None and result.quality["comparisons"] == 1
    assert result.quality["consistency_comparisons"] == 3
    assert "embedding" not in result.model_dump_json()


def test_ram_reference_does_not_read_an_input_path_and_stays_unclear_without_threshold(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("FACE_MATCH_CALIBRATION", raising=False)
    detector, inp = setup_detector(tmp_path)
    inp.reference_image = Path("never-open-reference.png")
    pixels = np.full((112, 112, 3), 80, np.uint8)
    result = detector.predict_frames(inp, {"front": pixels}, reference_frame=pixels // 2)
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR
    assert result.quality["comparisons"] == 1 and result.prob_attack is None


def test_card_match_uses_front_only_and_reports_cross_view_scores_separately(tmp_path):
    # Front matches reference; a low side-view score must not change the card match.
    a, b = 0.8 * vector() + 0.6 * vector(1), 0.8 * vector() - 0.6 * vector(1)
    detector, inp = setup_detector(tmp_path, vectors=[vector(), vector(), a, b], threshold=True)
    result = detector.predict(inp)
    scores = next(e.value for e in result.evidence if e.name == "cosine_similarities")
    views = next(e.value for e in result.evidence if e.name == "view_cosine_similarities")
    assert scores == {"reference_front": 1.0}
    assert len(views) == 3 and views["left_right"] == pytest.approx(0.28)
    assert not result.quality["consistency_verified"]
    assert result.status == Status.OK and result.gate == Gate.PASS
    assert result.score == 0
    assert result.prob_attack is None


@pytest.mark.parametrize("views", [1, 3])
def test_trusted_threshold_can_pass_matching_identity(tmp_path, views):
    detector, inp = setup_detector(tmp_path, threshold=True)
    inp.images, inp.image_roles = inp.images[:views], inp.image_roles[:views]
    result = detector.predict(inp)
    assert result.status == Status.OK and result.gate == Gate.PASS
    assert result.quality["comparisons"] == 1
    assert result.quality["consistency_comparisons"] == (0 if views == 1 else 3)


def test_in_memory_frames_separate_card_match_and_ignore_input_paths_roles(tmp_path):
    detector, inp = setup_detector(tmp_path, threshold=True)
    inp.images = [Path("never-open-client-query.png")]
    inp.image_roles = ["front"]
    frames = {
        role: np.full((112, 112, 3), 70 + i * 25, dtype=np.uint8)
        for i, role in enumerate(("front", "left", "right"))
    }
    result = detector.predict_frames(inp, frames)
    assert result.status == Status.OK and result.gate == Gate.PASS
    assert result.quality["comparisons"] == 1 and result.prob_attack is None
    assert result.quality["consistency_comparisons"] == 3


def test_side_views_cannot_rescue_a_mismatched_frontal_identity(tmp_path):
    detector, inp = setup_detector(
        tmp_path, vectors=[vector(), vector(1), vector(), vector()], threshold=True
    )
    result = detector.predict(inp)
    assert result.status == Status.OK and result.gate == Gate.FAIL
    assert result.score == 1


def test_old_six_pair_calibration_is_rejected_after_protocol_change(tmp_path):
    detector, inp = setup_detector(tmp_path)
    detector.calibration_path = artifact(
        tmp_path, model_version=MATCH_VERSION.removesuffix("+front-reference-v2")
    )
    result = detector.predict(inp)
    assert result.status == Status.ERROR and result.gate == Gate.UNCLEAR


def test_identical_reference_and_selfie_pixels_cannot_pass(tmp_path):
    detector, inp = setup_detector(tmp_path, threshold=True)
    inp.images, inp.image_roles = [inp.reference_image], ["front"]
    result = detector.predict(inp)
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR
    assert result.error_code == "E_INTEGRITY"
    assert not (tmp_path / "never-open-client-query.png").exists()


def test_repeated_in_memory_pixels_and_invalid_arrays_cannot_pass(tmp_path):
    detector, inp = setup_detector(tmp_path, threshold=True)
    frame = np.full((112, 112, 3), 70, dtype=np.uint8)
    result = detector.predict_frames(inp, {role: frame for role in ("front", "left", "right")})
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR
    detector, inp = setup_detector(tmp_path, threshold=True)
    assert detector.predict_frames(inp, {"front": np.zeros((112, 112))}).gate == Gate.UNCLEAR


@pytest.mark.parametrize(
    "change", ["missing_reference", "wrong_roles", "two_views", "reused_pixels"]
)
def test_missing_or_reused_view_evidence_never_passes(tmp_path, change):
    detector, inp = setup_detector(tmp_path, threshold=True)
    if change == "missing_reference":
        inp.reference_image = None
    elif change == "wrong_roles":
        inp.image_roles = ["front", "front", "right"]
    elif change == "two_views":
        inp.images, inp.image_roles = inp.images[:2], inp.image_roles[:2]
    else:
        inp.images[1] = inp.images[0]
    result = detector.predict(inp)
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR


@pytest.mark.parametrize(
    "faces,code", [([], "E_NO_FACE"), ([FaceBox(0, 0, 100, 100, 1)] * 2, "E_MULTI_FACE")]
)
def test_no_face_or_multiple_faces_never_pass(tmp_path, faces, code):
    detector, inp = setup_detector(tmp_path, threshold=True, faces=faces)
    result = detector.predict(inp)
    assert result.status == Status.NOT_APPLICABLE and result.error_code == code
    assert result.gate == Gate.UNCLEAR


@pytest.mark.parametrize(
    "changes", [{"model_version": "other-model"}, {"split": "test"}, {"threshold": 2}]
)
def test_invalid_or_wrong_model_calibration_fails_closed(tmp_path, changes):
    detector, inp = setup_detector(tmp_path)
    detector.calibration_path = artifact(tmp_path, **changes)
    assert detector.predict(inp).status == Status.ERROR
    assert detector.predict(inp).gate == Gate.UNCLEAR


def test_internal_input_contract_matches_new_fields_and_rejects_unknown_roles():
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "packages/contracts/schemas/detector_input.schema.json"
        ).read_text(encoding="utf-8")
    )
    inp = DetectorInput(
        reference_image=Path("reference.png"), images=[Path("front.png")], image_roles=["front"]
    )
    assert set(DetectorInput.model_fields) == set(schema["properties"])
    jsonschema.validate(inp.model_dump(mode="json"), schema)
    jsonschema.validate(DetectorInput().model_dump(mode="json"), schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"image_roles": ["profile"]}, schema)


def test_failed_onnx_provider_validation_cannot_leave_a_usable_session(monkeypatch):
    from vericlue_ml.face import match

    attempts = []

    def session(*args, **kwargs):
        attempts.append(1)
        return object()

    def reject(*args, **kwargs):
        raise RuntimeError("synthetic backend failure")

    monkeypatch.setattr(
        match, "_verified_weights", lambda *args: (Path("unused.onnx"), match.LVFACE_REVISION)
    )
    monkeypatch.setattr(match, "onnx_providers", lambda *args, **kwargs: ["CPUExecutionProvider"])
    monkeypatch.setattr(match, "check_onnx_session", reject)
    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(SessionOptions=SimpleNamespace, InferenceSession=session),
    )
    embedder = LVFaceEmbedder()
    with pytest.raises(RuntimeError):
        embedder.preload(device="cpu")
    assert embedder.session is None
    with pytest.raises(MatchError):
        embedder.embed(np.zeros((1, 3, 112, 112), dtype=np.float32))
    assert len(attempts) == 1
