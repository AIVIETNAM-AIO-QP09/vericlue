"""Server binding and exact selected pixels are required; no camera or biometric data."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Gate, ModuleResult, Status
from vericlue_ml.face import video_match
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION, VideoFaceMatchDetector
from vericlue_ml.presence.landmarks import FaceObservation
from vericlue_ml.presence.views import SelectedFrame


def inputs():
    return DetectorInput(
        session_id="ses_video",
        video=Path("server-video.mp4"),
        reference_image=Path("card.png"),
        images=[Path("never-read-still.png")],
        metadata={
            "challenge_id": "ch_current",
            "expected_challenge": {
                "challenge_id": "ch_current",
                "baseline_ms": 1000,
                "dynamic": {"session_id": "ses_video", "version": 1, "frontal_capture_at_ms": 250},
            },
        },
    )


def setup(monkeypatch, *, yaw=0.0, count=1, hashes=None):
    frame = np.full((112, 112, 3), 42, np.uint8)
    reader = SimpleNamespace(
        observe=lambda pixels, at_ms: FaceObservation(
            at_ms, count, yaw_deg=yaw, pitch_deg=0.0, roll_deg=0.0
        )
    )
    matcher = VideoFaceMatchDetector(reader=reader)
    calls = []

    def score(inp, frames):
        calls.append((inp, frames))
        assert frames.keys() == {"front"}
        assert frames["front"] is frame
        return ModuleResult(
            module="face_match",
            model_version=VIDEO_MATCH_VERSION,
            status="degraded",
            gate="unclear",
            score=0.2,
            latency_ms=0,
        )

    monkeypatch.setattr(matcher, "predict_frames", score)
    sequence = iter(hashes) if hashes else None
    monkeypatch.setattr(
        video_match, "video_sha256", lambda path: next(sequence) if sequence else "a" * 64
    )
    monkeypatch.setattr(
        video_match,
        "select_frontal_frame",
        lambda path, target: SelectedFrame(target, 240.0, frame),
    )
    return matcher, calls


def test_only_pose_checked_server_frame_reaches_matcher(monkeypatch):
    matcher, calls = setup(monkeypatch)
    result = matcher.predict(inputs())
    assert result.status == Status.DEGRADED and result.score == 0.2
    assert result.quality["frontal_pose_checked"] and len(calls) == 1
    selected = next(e.value for e in result.evidence if e.name == "selected_frontal_frame")
    assert selected["target_ms"] == 250 and selected["at_ms"] == 240


@pytest.mark.parametrize(
    "change", ["session", "challenge", "missing_video", "missing_plan", "after_baseline"]
)
def test_wrong_server_binding_never_falls_back_to_a_still(monkeypatch, change):
    matcher, calls = setup(monkeypatch)
    inp = inputs()
    if change == "session":
        inp.session_id = "ses_other"
    elif change == "challenge":
        inp.metadata["challenge_id"] = "ch_old"
    elif change == "missing_video":
        inp.video = None
    elif change == "missing_plan":
        inp.metadata = {}
    else:
        inp.metadata["expected_challenge"]["dynamic"]["frontal_capture_at_ms"] = 1000
    result = matcher.predict(inp)
    assert result.gate == Gate.UNCLEAR and result.status != Status.OK
    assert not calls


@pytest.mark.parametrize("yaw,count", [(25.0, 1), (float("nan"), 1), (0.0, 0), (0.0, 2)])
def test_bad_pose_or_face_count_cannot_reach_identity_model(monkeypatch, yaw, count):
    matcher, calls = setup(monkeypatch, yaw=yaw, count=count)
    result = matcher.predict(inputs())
    assert result.gate == Gate.UNCLEAR and not calls


@pytest.mark.parametrize("hashes,scored", [(["a", "b"], False), (["a", "a", "b"], True)])
def test_mutated_video_cannot_keep_a_successful_result(monkeypatch, hashes, scored):
    matcher, calls = setup(monkeypatch, hashes=hashes)
    result = matcher.predict(inputs())
    assert result.error_code == "E_INTEGRITY" and result.gate == Gate.UNCLEAR
    assert result.score is None and bool(calls) == scored
