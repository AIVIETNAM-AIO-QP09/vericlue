"""Opt-in checkpoint/CLI smoke on generated blank frames, zero human samples."""

import importlib.util
import json
import os

import numpy as np
import pytest

from vericlue_ml.eval.gaze_video import main


@pytest.mark.slow
def test_real_chromapulse_cli_blank_video_is_unclear(tmp_path):
    root = os.environ.get("GAZE_MODELS_DIR")
    if not root or importlib.util.find_spec("mediapipe") is None:
        pytest.skip("GAZE_MODELS_DIR and an isolated MediaPipe runtime are required")
    cv2 = pytest.importorskip("cv2")
    video = tmp_path / "synthetic-blank.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    assert writer.isOpened()
    try:
        for _ in range(63):
            writer.write(np.full((240, 320, 3), 110, dtype=np.uint8))
    finally:
        writer.release()
    response = tmp_path / "synthetic-server-response.json"
    palette = ("#ffcc73", "#73d9ff", "#ffb3eb", "#80e09e")
    response.write_text(
        json.dumps(
            {
                "session_id": "ses_synthetic",
                "challenge": {
                    "challenge_id": "ch_synthetic",
                    "baseline_ms": 1000,
                    "color_sequence": [
                        {"rgb": palette[i % 4], "hold_ms": 500, "transition_ms": 150}
                        for i in range(8)
                    ],
                    "dynamic": {
                        "version": 1,
                        "session_id": "ses_synthetic",
                        "gaze_points": [{"at_ms": 6200}],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "diagnostic.json"
    assert (
        main(
            [
                "--module",
                "chromapulse",
                "--video",
                str(video),
                "--server-response",
                str(response),
                "--models-dir",
                root,
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    result = payload["result"]
    assert result["status"] == "degraded" and result["gate"] == "unclear"
    assert result["error_code"] == "E_NO_FACE"
    assert "prob_attack" not in result and "score" not in result
    assert payload["sample_count"] == 1 and payload["model_sha256"]
    assert payload["commit"] and payload["dataset"] == "local_diagnostic_not_accuracy_evaluation"
    assert len(payload["video_sha256"]) == 64
    assert any(row["name"] == "color_config_sha256" for row in result["evidence"])
