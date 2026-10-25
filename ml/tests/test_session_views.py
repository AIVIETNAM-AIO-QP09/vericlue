"""Selected session attack/consistency frames must match server schedule and observed pose."""

from types import SimpleNamespace

import numpy as np
import pytest
from test_video_frontal_match import inputs

from vericlue_ml.common.result import Evidence, ModuleResult
from vericlue_ml.presence import session_views as selection
from vericlue_ml.presence.landmarks import FaceObservation, LandmarkError
from vericlue_ml.presence.views import SelectedFrame


@pytest.mark.parametrize("fault", [None, "head_failed", "time", "pose", "faces", "changed"])
def test_session_frame_selection_rejects_missing_or_wrong_evidence(monkeypatch, fault):
    inp = inputs()
    inp.metadata["expected_challenge"]["dynamic"].update(
        head_start_at_ms=12000, head_duration_ms=6000, head_turns=["left", "right", "center"]
    )
    times = {"front": 250, "left": 13000, "right": 15000}
    if fault == "time":
        times["front"] = 350
    head = ModuleResult(
        module="head_turn",
        model_version="synthetic",
        status="ok",
        gate="fail" if fault == "head_failed" else "pass",
        latency_ms=0,
        evidence=[Evidence(type="scalar", name="view_times_ms", value=times)],
    )
    monkeypatch.setattr(
        selection, "HeadTurnDetector", lambda *_: SimpleNamespace(predict=lambda _: head)
    )
    monkeypatch.setattr(
        selection, "video_sha256", lambda *_: "a" if fault != "changed" else next(hashes)
    )
    hashes = iter(["a", "b"])
    frames = {
        role: SelectedFrame(time, time, np.full((20, 20, 3), i, np.uint8))
        for i, (role, time) in enumerate(times.items())
    }
    monkeypatch.setattr(selection, "select_video_frames", lambda *_: frames)

    def observe(pixels, *, at_ms):
        yaw = {0: 0.0, 1: 28.0, 2: -28.0}[int(pixels[0, 0, 0])]
        return FaceObservation(
            at_ms,
            2 if fault == "faces" else 1,
            yaw_deg=0.0 if fault == "pose" else yaw,
            pitch_deg=0.0,
            roll_deg=0.0,
        )

    if fault is None:
        actual, checksum = selection.session_views(inp, SimpleNamespace(observe=observe))
        assert checksum == "a" and all(actual[role] is frames[role].bgr for role in frames)
    else:
        with pytest.raises(LandmarkError):
            selection.session_views(inp, SimpleNamespace(observe=observe))
