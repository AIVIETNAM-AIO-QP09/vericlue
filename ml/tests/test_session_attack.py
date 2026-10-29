"""A different sampling protocol cannot silently reuse a legacy attack calibrator."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Gate, ModuleResult, Status
from vericlue_ml.face import session_attack
from vericlue_ml.face.session_attack import SessionAttackDetector


@pytest.mark.parametrize("module", ["face_pad", "face_deepfake"])
def test_session_view_scores_stay_raw_and_use_exact_selected_arrays(monkeypatch, module):
    frames = {
        role: np.full((112, 112, 3), i * 30, np.uint8)
        for i, role in enumerate(("front", "left", "right"), 1)
    }

    class Backend:
        name = module
        frames_version = "synthetic-3views"

        def predict_frames(self, inp, actual):
            assert actual is frames
            return ModuleResult(
                module=module,
                model_version=self.frames_version,
                status="ok",
                score=0.2,
                prob_attack=0.01,
                gate="pass",
                latency_ms=1,
            )

    monkeypatch.setattr(session_attack, "session_views", lambda *_: (frames, "a" * 64))
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "a" * 64)
    result = SessionAttackDetector(Backend(), SimpleNamespace()).predict(
        DetectorInput(video=Path("server-video.mp4"), images=[Path("not-opened.png")])
    )
    assert result.status == Status.DEGRADED and result.gate == Gate.UNCLEAR
    assert result.score == 0.2 and result.prob_attack is None
    assert result.model_version.endswith("+session-video-v1")


def test_changed_video_discards_attack_measurement(monkeypatch):
    backend = SimpleNamespace(
        name="face_pad",
        frames_version="fake",
        predict_frames=lambda *_: ModuleResult(
            module="face_pad", model_version="fake", status="ok", score=0.2, latency_ms=0
        ),
    )
    monkeypatch.setattr(session_attack, "session_views", lambda *_: ({}, "a" * 64))
    monkeypatch.setattr(session_attack, "video_sha256", lambda *_: "b" * 64)
    result = SessionAttackDetector(backend, SimpleNamespace()).predict(
        DetectorInput(video=Path("fake.mp4"))
    )
    assert result.status == Status.ERROR and result.score is None
    assert result.error_code == "E_INTEGRITY"
