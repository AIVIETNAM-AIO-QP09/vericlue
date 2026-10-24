"""Optional real-checkpoint smoke; only synthetic blank frames, no biometric data."""

import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.presence.gaze import GazeDetector
from vericlue_ml.presence.landmarks import FaceObservationReader


@pytest.mark.slow
def test_real_model_reuses_task_and_blank_video_never_passes(tmp_path):
    root = os.environ.get("GAZE_MODELS_DIR")
    if not root or importlib.util.find_spec("mediapipe") is None:
        pytest.skip("GAZE_MODELS_DIR and the isolated MediaPipe runtime enable this smoke test")
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "synthetic-no-face.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    assert writer.isOpened()
    try:
        for index in range(141):
            writer.write(np.full((240, 320, 3), 100 + index % 10, dtype=np.uint8))
    finally:
        writer.release()
    points = [
        (0.5, 0.5),
        (0.2, 0.7),
        (0.8, 0.3),
        (0.3, 0.2),
        (0.7, 0.8),
        (0.2, 0.4),
        (0.6, 0.2),
        (0.8, 0.7),
    ]
    reader = FaceObservationReader()
    try:
        reader.preload(models_dir=Path(root))
        task = reader._task
        reader.preload()
        assert reader._task is task
        detector = GazeDetector(reader)
        for session_id in ("ses_synthetic_a", "ses_synthetic_b"):
            challenge = {
                "challenge_id": "ch_" + session_id,
                "dynamic": {
                    "version": 1,
                    "session_id": session_id,
                    "gaze_points": [
                        {"x": x, "y": y, "at_ms": 5000 + index * 1000}
                        for index, (x, y) in enumerate(points)
                    ],
                },
            }
            result = detector.predict(
                DetectorInput(
                    session_id=session_id,
                    video=path,
                    metadata={
                        "challenge_id": challenge["challenge_id"],
                        "expected_challenge": challenge,
                    },
                )
            )
            assert result.status == "not_applicable"
            assert result.error_code == "E_NO_FACE"
            assert result.gate == "unclear" and result.prob_attack is None
    finally:
        reader.close()
