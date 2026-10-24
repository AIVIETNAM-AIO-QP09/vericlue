"""FS-VFM wrapper behavior without weights, GPU or biometric fixtures."""

import os
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Status
from vericlue_ml.face.fsvfm import MEAN, STD, FsvfmPadDetector, face_tensor
from vericlue_ml.face.pad import FaceBox


def frames():
    return {
        role: np.full((140, 160, 3), [30 + i * 10, 80, 130], dtype=np.uint8)
        for i, role in enumerate(("front", "left", "right"))
    }


class Finder:
    def __init__(self, count=1, small=False):
        self.count, self.small = count, small

    def find(self, frame):
        return [
            FaceBox(
                30,
                20,
                50 if self.small else 130,
                120,
                0.99,
                [(64, 66), (96, 66), (80, 84), (67, 102), (93, 102)],
            )
        ] * self.count


class Classifier:
    def __init__(self, scores=None):
        self.scores = scores if scores is not None else [0.1, 0.8, 0.4]
        self.batches = []

    def p_fake(self, batch):
        self.batches.append(batch)
        return self.scores


def test_raw_pad_measurement_keeps_all_views_and_uses_distinct_version():
    classifier = Classifier()
    detector = FsvfmPadDetector(finder=Finder(), classifier=classifier)
    result = detector.predict_frames(DetectorInput(images=[Path("never-open.png")]), frames())
    assert result.status == Status.OK and result.score == 0.8
    assert result.gate is None and result.prob_attack is None
    assert result.model_version == detector.frames_version != detector.version
    assert result.quality["upstream_crop_parity"] is False
    batch = classifier.batches[0]
    assert batch.shape == (3, 3, 224, 224) and batch.dtype == np.float32
    expected = (np.array([130, 80, 30]) / 255 - np.array(MEAN)) / np.array(STD)
    np.testing.assert_allclose(batch[0, :, 112, 112], expected, atol=1e-6)


@pytest.mark.parametrize("kind", ["missing", "repeated", "dtype", "large", "empty"])
def test_invalid_frames_block_before_loading(kind):
    data = frames()
    if kind == "missing":
        del data["left"]
    elif kind == "repeated":
        data["left"] = data["right"]
    elif kind == "dtype":
        data["left"] = data["left"].astype(float)
    elif kind == "large":
        data["left"] = np.zeros((1081, 1920, 3), np.uint8)
    else:
        data["left"] = np.zeros((0, 20, 3), np.uint8)
    detector = FsvfmPadDetector()
    detector.preload = lambda **kwargs: pytest.fail("invalid frames must not load model")
    result = detector.predict_frames(DetectorInput(), data)
    assert result.status == Status.DEGRADED and result.score is None


@pytest.mark.parametrize("count,code", [(0, "E_NO_FACE"), (2, "E_MULTI_FACE")])
def test_one_face_per_view_required(count, code):
    classifier = Classifier()
    result = FsvfmPadDetector(finder=Finder(count), classifier=classifier).predict_frames(
        DetectorInput(), frames()
    )
    assert result.error_code == code and not classifier.batches


def test_small_face_rejected_and_single_image_interface_does_not_accept_video():
    detector = FsvfmPadDetector(finder=Finder(small=True), classifier=Classifier())
    assert detector.predict_frames(DetectorInput(), frames()).error_code == "E_LOW_QUALITY"
    assert detector.predict(DetectorInput(video=Path("never-open.mp4"))).error_code == "E_DECODE"


@pytest.mark.parametrize(
    "scores", [[0.1], [float("nan"), 0.2, 0.3], [-0.1, 0.2, 0.3], [1.1, 0.2, 0.3]]
)
def test_bad_scores_never_become_measurements(scores):
    result = FsvfmPadDetector(finder=Finder(), classifier=Classifier(scores)).predict_frames(
        DetectorInput(), frames()
    )
    assert result.status == Status.ERROR and result.score is None and result.prob_attack is None


def test_factory_preserves_legacy_and_mock_does_not_import_torch():
    from vericlue_ml.registry import get_detector, get_fsvfm_pad

    assert get_detector("face_pad", mock=False).__class__.__name__ == "FacePadDetector"
    assert isinstance(get_fsvfm_pad(), FsvfmPadDetector)
    mock = get_fsvfm_pad(mock=True)
    assert mock.predict_frames(DetectorInput(), frames()).module == "face_pad"


def test_preload_uses_rgb_scrfd_normalization_and_reuses_models(monkeypatch, tmp_path):
    from vericlue_ml.face import fsvfm

    calls = []
    classifier = Classifier()
    monkeypatch.setattr(fsvfm, "shared_scrfd_session", lambda *args: ("session", "det-revision"))
    monkeypatch.setattr(fsvfm, "load_classifier", lambda *args: (classifier, "pad-revision"))

    def finder(session, **kwargs):
        calls.append((session, kwargs))
        return Finder()

    monkeypatch.setattr(fsvfm, "ScrfdFaceFinder", finder)
    detector = FsvfmPadDetector(models_dir=tmp_path)
    detector.preload(device="cpu")
    detector.preload(models_dir=tmp_path, device="cpu")
    assert calls == [("session", {"scale": 128.0, "swap_rb": True})]
    assert detector._classifier is classifier
    with pytest.raises(fsvfm.PadError):
        detector.preload(models_dir=tmp_path / "other")


@pytest.mark.slow
def test_original_checkpoint_cpu_forward_and_no_face_guard():
    root = os.environ.get("FSVFM_MODELS_DIR")
    if not root:
        pytest.skip("FSVFM_MODELS_DIR enables original FS-VFM-L FP32 CPU smoke")
    pytest.importorskip("torch")
    detector = FsvfmPadDetector(models_dir=Path(root))
    detector.preload(device="cpu")
    cached = detector._classifier
    p = cached.p_fake(face_tensor(np.full((112, 112, 3), 127, np.uint8))[None])
    assert len(p) == 1 and 0 <= p[0] <= 1 and np.isfinite(p[0])
    assert sum(t.numel() for t in cached.network.parameters()) > 300_000_000
    result = detector.predict_frames(DetectorInput(), frames())
    assert result.error_code == "E_NO_FACE" and result.prob_attack is None
    detector.preload(models_dir=Path(root), device="cpu")
    assert detector._classifier is cached
