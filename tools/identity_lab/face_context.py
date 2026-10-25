"""Optional no-face recovery for tightly cropped inputs, without lowering confidence."""

import copy
import hashlib
from pathlib import Path

import cv2
import numpy as np
from face_matching import pipeline_config


class ContextDetector:
    def __init__(self, detector):
        self.detector = detector

    def __getattr__(self, name):
        return getattr(self.detector, name)

    def detect(self, image):
        faces = self.detector.detect(image)
        if len(faces) != 0:
            return faces
        h, w = image.shape[:2]
        top, left = h // 2, w // 2
        padded = cv2.copyMakeBorder(
            image, top, top, left, left, cv2.BORDER_CONSTANT, value=(127, 127, 127)
        )
        recovered = self.detector.detect(padded)
        result = []
        for face in recovered:
            mapped = copy.copy(face)
            mapped.bbox = np.asarray(face.bbox, dtype=float) - [left, top, left, top]
            mapped.landmarks = np.asarray(face.landmarks, dtype=float) - [left, top]
            # Do not clip geometry or discard extra faces. Existing validation decides retry.
            result.append(mapped)
        return result


def enable_context(lab):
    lab._load_faces()
    if not isinstance(lab._detector, ContextDetector):
        lab._detector = ContextDetector(lab._detector)


def context_config(lab):
    config = pipeline_config(lab)
    if isinstance(lab._detector, ContextDetector):
        config["no_face_recovery"] = {
            "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "padding_each_side_fraction": 0.5,
            "padding_bgr": [127, 127, 127],
            "trigger": "zero detections only; retain confidence and NMS thresholds",
            "alignment": "original pixels with translated landmarks; no padding in recognizer input",
        }
    return config
