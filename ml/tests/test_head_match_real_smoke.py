"""Optional original-checkpoint smoke on blank video/pixels; no accuracy claims."""

import os
from pathlib import Path

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.face.match import FaceMatchDetector, LVFaceEmbedder, match_tensor
from vericlue_ml.presence.head_turn import HeadTurnDetector
from vericlue_ml.presence.landmarks import FaceObservationReader


@pytest.mark.slow
def test_original_lvface_inference_normalizes_reuses_session_and_rejects_blank_face(tmp_path):
    root = os.environ.get("FACE_MATCH_MODELS_DIR")
    if not root:
        pytest.skip("FACE_MATCH_MODELS_DIR enables original LVFace/SCRFD CPU smoke")
    pytest.importorskip("onnxruntime")
    cv2 = pytest.importorskip("cv2")
    embedder = LVFaceEmbedder()
    embedder.preload(models_dir=Path(root), device="cpu")
    session = embedder.session
    tensor = match_tensor(np.full((112, 112, 3), 127, dtype=np.uint8))
    first, second = embedder.embed(tensor), embedder.embed(tensor)
    assert first.shape == (512,) and np.isfinite(first).all()
    assert np.linalg.norm(first) == pytest.approx(1.0)
    np.testing.assert_allclose(first, second, atol=1e-6)
    assert embedder.session is session
    blank = tmp_path / "synthetic-blank.png"
    assert cv2.imwrite(str(blank), np.full((240, 320, 3), 127, dtype=np.uint8))
    detector = FaceMatchDetector(embedder=embedder)
    detector.preload(models_dir=Path(root), device="cpu")
    result = detector.predict(
        DetectorInput(reference_image=blank, images=[blank], image_roles=["front"])
    )
    assert result.status == "not_applicable" and result.error_code == "E_NO_FACE"
    assert result.gate == "unclear" and result.prob_attack is None


@pytest.mark.slow
def test_real_head_task_is_reused_and_no_face_never_passes(tmp_path):
    root = os.environ.get("HEAD_MODELS_DIR")
    if not root:
        pytest.skip("HEAD_MODELS_DIR enables isolated MediaPipe CPU smoke")
    pytest.importorskip("mediapipe")
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "synthetic-no-face.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    assert writer.isOpened()
    try:
        for index in range(191):
            writer.write(np.full((240, 320, 3), 100 + index % 10, dtype=np.uint8))
    finally:
        writer.release()
    reader = FaceObservationReader()
    try:
        reader.preload(models_dir=Path(root))
        task = reader._task
        for session_id in ("ses_head_a", "ses_head_b"):
            reader.preload()
            assert reader._task is task
            challenge = {
                "challenge_id": "ch_" + session_id,
                "dynamic": {
                    "version": 1,
                    "session_id": session_id,
                    "head_start_at_ms": 12000,
                    "head_duration_ms": 6000,
                    "frontal_capture_at_ms": 1000,
                    "head_turns": ["left", "right", "center"],
                },
            }
            result = HeadTurnDetector(reader).predict(
                DetectorInput(
                    session_id=session_id,
                    video=path,
                    metadata={
                        "challenge_id": challenge["challenge_id"],
                        "expected_challenge": challenge,
                    },
                )
            )
            assert result.status == "not_applicable" and result.gate == "unclear"
            assert result.prob_attack is None
            assert result.quality["depth_verified"] is False
    finally:
        reader.close()
