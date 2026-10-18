"""Optional local parity against UniFace 4.0.0; no media/embeddings are saved."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from make_image_splits import FaceEncoder  # noqa: E402

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def parity_encoders():
    root = os.environ.get("DATA03_PARITY_MODELS")
    data = os.environ.get("DATA03_PARITY_DATA")
    if not root or not data:
        pytest.skip("Set DATA03_PARITY_MODELS and DATA03_PARITY_DATA for local parity")
    uniface = pytest.importorskip("uniface")
    assert uniface.__version__ == "4.0.0"
    from uniface.detection import SCRFD
    from uniface.recognition import ArcFace

    encoder = FaceEncoder(Path(root))
    # Reuse already verified sessions: reference never downloads models.
    detector = object.__new__(SCRFD)
    detector._num_feature_maps = 3
    detector._feat_stride_fpn = [8, 16, 32]
    detector._num_anchors = 2
    detector._center_cache = {}
    detector.confidence_threshold = 0.5
    detector.nms_threshold = 0.4
    detector.input_size = (640, 640)
    detector.session = encoder.detector
    detector.input_names = encoder.det_input
    detector.output_names = [x.name for x in encoder.detector.get_outputs()]
    recognizer = object.__new__(ArcFace)
    recognizer.input_mean = 127.5
    recognizer.input_std = 127.5
    recognizer.input_size = (112, 112)
    recognizer.session = encoder.recognizer
    recognizer.input_name = encoder.rec_input
    recognizer.output_names = [x.name for x in encoder.recognizer.get_outputs()]
    paths = sorted((Path(data) / "raw/fas_vn/extracted/Image/test_photo/live").glob("*.jpg"))[:3]
    assert len(paths) == 3
    yield encoder, detector, recognizer, paths
    encoder.close()


@pytest.mark.parametrize("index", range(3))
def test_detector_landmarks_and_arcface_embedding_match_reference(parity_encoders, index):
    import cv2

    encoder, detector, recognizer, paths = parity_encoders
    frame = cv2.imread(str(paths[index]))
    reference_faces = detector.detect(frame)
    landmarks = encoder.landmarks(frame)
    assert len(landmarks) == len(reference_faces) > 0
    actual = encoder.encode(paths[index])
    cosines = []
    for points, face, vector in zip(landmarks, reference_faces, actual, strict=True):
        np.testing.assert_allclose(points, face.landmarks, atol=1e-4, rtol=0)
        expected = recognizer.get_normalized_embedding(frame, face.landmarks)
        cosine = float(np.dot(vector, expected))
        assert cosine >= 0.9999
        cosines.append(cosine)
    print(f"image {index}: faces={len(landmarks)}, cosine_min={min(cosines):.8f}")
