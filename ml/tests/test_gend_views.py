"""GenD on targeted RAM views: no GPU, weights or biometric fixtures."""

import json
import os
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Status
from vericlue_ml.face.gend import CLIP_MEAN, CLIP_STD, FaceDeepfakeDetector
from vericlue_ml.face.pad import FaceBox


def frames():
    return {
        role: np.full((140, 160, 3), [30 + i * 10, 80, 130], dtype=np.uint8)
        for i, role in enumerate(("front", "left", "right"))
    }


class Finder:
    def __init__(self, count=1):
        self.count = count

    def find(self, image):
        return [
            FaceBox(30, 20, 130, 120, 0.99, [(64, 66), (96, 66), (80, 84), (67, 102), (93, 102)])
        ] * self.count


class Classifier:
    def __init__(self, scores=None):
        self.scores = scores if scores is not None else [0.1, 0.3, 0.9]
        self.calls = []

    def p_fake(self, batch):
        self.calls.append(batch)
        return self.scores


def test_views_preserve_rgb_clip_preprocessing_and_raw_aggregation():
    classifier = Classifier()
    detector = FaceDeepfakeDetector(finder=Finder(), classifier=classifier)
    legacy_version = detector.version
    inp = DetectorInput(
        video=Path("never-open.webm"), images=[Path("never-open.png")], image_roles=["front"]
    )
    result = detector.predict_frames(inp, frames())
    assert result.status == Status.OK and result.score == pytest.approx(0.9)
    assert result.prob_attack is None and result.gate is None
    assert result.model_version == legacy_version + "+headturn-3views-v1"
    assert detector.version == legacy_version  # Legacy calibrator identity remains unchanged.
    assert classifier.calls[0].shape == (3, 3, 224, 224)
    expected = (np.array([130, 80, 30]) / 255 - np.array(CLIP_MEAN)) / np.array(CLIP_STD)
    np.testing.assert_allclose(classifier.calls[0][0, :, 112, 112], expected, atol=1e-6)
    assert next(e.value for e in result.evidence if e.name == "view_scores") == {
        "front": 0.1,
        "left": 0.3,
        "right": 0.9,
    }
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "packages/contracts/schemas/module_result.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.validate(result.to_contract(), schema)


@pytest.mark.parametrize("kind", ["missing", "bad_array", "repeated", "large"])
def test_invalid_views_do_not_preload_or_score(kind):
    classifier = Classifier()
    detector = FaceDeepfakeDetector(finder=Finder(), classifier=classifier)
    values = frames()
    if kind == "missing":
        del values["left"]
    elif kind == "bad_array":
        values["front"] = np.zeros((140, 160))
    elif kind == "repeated":
        values["left"] = values["front"]
    else:
        values["front"] = np.zeros((1081, 1920, 3), dtype=np.uint8)
    detector.preload = lambda **kwargs: pytest.fail("invalid input must not preload")
    result = detector.predict_frames(DetectorInput(), values)
    assert result.status == Status.DEGRADED and result.prob_attack is None and not classifier.calls


@pytest.mark.parametrize("count,code", [(0, "E_NO_FACE"), (2, "E_MULTI_FACE")])
def test_exactly_one_face_required_in_every_view(count, code):
    classifier = Classifier()
    result = FaceDeepfakeDetector(finder=Finder(count), classifier=classifier).predict_frames(
        DetectorInput(), frames()
    )
    assert result.status == Status.NOT_APPLICABLE and result.error_code == code
    assert not classifier.calls and result.score is None


@pytest.mark.parametrize(
    "scores", [[0.1], [0.1, float("nan"), 0.9], [-0.1, 0.3, 0.9], [1.1, 0.3, 0.9]]
)
def test_invalid_classifier_outputs_never_become_measurements(scores):
    result = FaceDeepfakeDetector(finder=Finder(), classifier=Classifier(scores)).predict_frames(
        DetectorInput(), frames()
    )
    assert result.status == Status.ERROR and result.score is None and result.prob_attack is None


def test_legacy_predict_does_not_adopt_targeted_view_version():
    detector = FaceDeepfakeDetector(finder=Finder(), classifier=Classifier())
    result = detector.predict(DetectorInput())
    assert result.model_version == detector.version
    assert result.model_version != detector.frames_version


@pytest.mark.slow
def test_original_gend_weights_infer_and_ram_views_reject_faceless_input():
    root = os.environ.get("GEND_VIEWS_MODELS_DIR")
    if not root:
        pytest.skip("GEND_VIEWS_MODELS_DIR enables original GenD/SCRFD CPU smoke")
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    detector = FaceDeepfakeDetector(models_dir=Path(root))
    detector.preload(device="cpu")
    classifier = detector._classifier
    values = classifier.p_fake(np.zeros((1, 3, 224, 224), dtype=np.float32))
    assert len(values) == 1 and np.isfinite(values[0]) and 0 <= values[0] <= 1
    result = detector.predict_frames(DetectorInput(), frames())
    assert result.status == Status.NOT_APPLICABLE and result.error_code == "E_NO_FACE"
    assert result.prob_attack is None and result.gate is None
    assert detector._classifier is classifier and result.model_version == detector.frames_version
