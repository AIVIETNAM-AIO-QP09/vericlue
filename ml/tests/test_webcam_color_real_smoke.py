"""Optional one-frame native landmark smoke; zero camera access or human data."""

import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.eval.webcam_color import observe_live
from vericlue_ml.presence.landmarks import FaceObservationReader


@pytest.mark.slow
def test_native_face_and_color_observations_share_one_task_on_blank_frame():
    root = os.environ.get("GAZE_MODELS_DIR")
    if not root or importlib.util.find_spec("mediapipe") is None:
        pytest.skip("GAZE_MODELS_DIR and isolated MediaPipe runtime are required")
    reader = FaceObservationReader()
    try:
        reader.preload(models_dir=Path(root))
        task = reader._task
        frame = np.full((240, 320, 3), 110, np.uint8)
        face, color = observe_live(reader, frame, with_color=True)
        assert reader._task is task and face.face_count == color.face_count == 0
        assert not color.regions
        assert observe_live(reader, frame, with_color=False)[1] is None
        assert reader._task is task
    finally:
        reader.close()
