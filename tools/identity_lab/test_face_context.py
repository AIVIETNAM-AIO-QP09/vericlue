from types import SimpleNamespace

import numpy as np
import pytest
from face_context import ContextDetector
from face_matching import validate_face
from identity_lab import InputError


class Detector:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.inputs = []

    def detect(self, image):
        self.inputs.append(image)
        return next(self.outputs)


@pytest.mark.parametrize("count", [1, 2])
def test_existing_faces_do_not_trigger_retry(count):
    faces = [object() for _ in range(count)]
    detector = Detector([faces])
    assert ContextDetector(detector).detect(np.zeros((100, 100, 3))) is faces
    assert len(detector.inputs) == 1


def test_recovery_translates_geometry_without_mutation_or_clipping():
    face = SimpleNamespace(
        bbox=np.array([45, 60, 140, 145]),
        landmarks=np.array([[70, 80], [110, 80], [90, 100], [75, 120], [105, 120]]),
        confidence=0.9,
    )
    detector = Detector([[], [face, face]])
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    result = ContextDetector(detector).detect(image)
    assert len(result) == 2
    assert detector.inputs[1].shape == (200, 200, 3)
    assert np.all(detector.inputs[1][:50] == 127)
    np.testing.assert_array_equal(detector.inputs[1][50:150, 50:150], image)
    np.testing.assert_array_equal(result[0].bbox, [-5, 10, 90, 95])
    np.testing.assert_array_equal(result[0].landmarks, face.landmarks - [50, 50])
    np.testing.assert_array_equal(face.bbox, [45, 60, 140, 145])
    with pytest.raises(InputError, match="E_FACE_CLIPPED"):
        validate_face(result[0], image, "reference")


def test_failed_recovery_remains_empty():
    detector = Detector([[], []])
    assert ContextDetector(detector).detect(np.zeros((100, 100, 3))) == []
    assert len(detector.inputs) == 2
