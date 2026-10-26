"""Enrolled-reference protocols use trusted pixels, private vectors and separate artifacts."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.face import enrolled
from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION, RECOVERY_MATCH_VERSION, match_enrolled
from vericlue_ml.face.match import MatchThreshold
from vericlue_ml.face.template import FaceTemplate
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION, VideoFaceMatchDetector
from vericlue_ml.presence.landmarks import FaceObservation
from vericlue_ml.presence.views import SelectedFrame


def threshold(version):
    return dict(
        model_version=version,
        preprocessing="arcface112-rgb-minus1to1-v1",
        threshold=0.8,
        split="calib_ltt",
        dataset="synthetic-engineering-test",
        pairs=4,
        subjects=2,
        source_commit="a" * 40,
        predictions_sha256="b" * 64,
    )


def setup(monkeypatch, tmp_path, *, recovery=False):
    frames = {
        name: np.full((112, 112, 3), i, np.uint8)
        for i, name in enumerate(("front", "left", "right"), 1)
    }
    reader = SimpleNamespace(
        observe=lambda frame, at_ms: FaceObservation(
            at_ms, 1, yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0
        )
    )
    matcher = VideoFaceMatchDetector(reader=reader)
    matcher._consistency_threshold = MatchThreshold(
        **threshold(VIDEO_MATCH_VERSION + "+view-consistency-v1")
    )
    vector = np.asarray([1.0] + [0.0] * 511)
    calls = []

    def embed(selected):
        calls.append(set(selected))
        return {
            name: (vector.copy(), hashlib.sha256(frame.tobytes()).hexdigest())
            for name, frame in selected.items()
        }

    monkeypatch.setattr(matcher, "embed_frames", embed)
    monkeypatch.setattr(enrolled, "video_sha256", lambda _: "c" * 64)
    targets = []

    def select(path, target):
        targets.append(target)
        return SelectedFrame(target, float(target), frames["front"])

    monkeypatch.setattr(enrolled, "select_frontal_frame", select)
    monkeypatch.setattr(enrolled, "session_views", lambda inp, reader: (frames.copy(), "c" * 64))
    inp = DetectorInput(
        session_id="ses_current",
        video=Path("server-video.mp4"),
        images=[Path("client-must-not-be-read.jpg")],
        reference_image=Path("must-not-read-card.jpg"),
        signals={"target_ms": 0, "threshold": -1},
        metadata={
            "purpose": "recovery" if recovery else "reauth",
            "account_id": "acct_" + "a" * 32,
            "challenge_id": "ch_current",
            "expected_challenge": {
                "challenge_id": "ch_current",
                "dynamic": {
                    "version": 1,
                    "session_id": "ses_current",
                    "frontal_capture_at_ms": 250,
                },
            },
        },
    )
    template = FaceTemplate(
        session_id="ses_enrolled",
        challenge_id="ch_enrolled",
        model_version=VIDEO_MATCH_VERSION,
        preprocessing="arcface112-rgb-minus1to1-v1",
        source_video_sha256="d" * 64,
        pixels_sha256="e" * 64,
        embedding=tuple(vector),
    )
    artifact = tmp_path / "threshold.json"
    artifact.write_text(
        json.dumps(threshold(RECOVERY_MATCH_VERSION if recovery else REAUTH_MATCH_VERSION))
    )
    return matcher, inp, template, artifact, targets, calls


@pytest.mark.parametrize("recovery", [False, True])
def test_server_pixels_only_match_front_to_enrolled_template(monkeypatch, tmp_path, recovery):
    matcher, inp, template, artifact, targets, calls = setup(
        monkeypatch, tmp_path, recovery=recovery
    )
    result = match_enrolled(matcher, inp, template, artifact)
    assert result.status == "ok" and result.gate == "pass"
    assert result.model_version == (RECOVERY_MATCH_VERSION if recovery else REAUTH_MATCH_VERSION)
    assert calls == [{"front", "left", "right"} if recovery else {"front"}]
    assert targets == [250 if recovery else 500]
    assert not result.quality["depth_verified"]
    assert "embedding" not in result.model_dump_json()
    assert "1.0,0.0" not in result.model_dump_json()


@pytest.mark.parametrize("recovery", [False, True])
def test_missing_calibrator_cannot_pass_even_with_identical_vectors(
    monkeypatch, tmp_path, recovery
):
    matcher, inp, template, _, _, _ = setup(monkeypatch, tmp_path, recovery=recovery)
    result = match_enrolled(matcher, inp, template, None)
    assert result.status == "degraded" and result.gate == "unclear"


@pytest.mark.parametrize(
    "fault",
    [
        "cccd_calibrator",
        "different_protocol",
        "bad_template",
        "mutated_video",
        "bad_pose",
        "missing_consistency",
        "duplicate_views",
        "different_front",
    ],
)
def test_wrong_protocol_or_untrusted_evidence_never_passes(monkeypatch, tmp_path, fault):
    matcher, inp, template, artifact, _, _ = setup(monkeypatch, tmp_path, recovery=True)
    if fault in {"cccd_calibrator", "different_protocol"}:
        artifact.write_text(
            json.dumps(
                threshold(
                    VIDEO_MATCH_VERSION if fault == "cccd_calibrator" else REAUTH_MATCH_VERSION
                )
            )
        )
    elif fault == "bad_template":
        template = template.model_copy(update={"embedding": (float("nan"),)})
    elif fault == "mutated_video":
        hashes = iter(["c" * 64, "f" * 64])
        monkeypatch.setattr(enrolled, "video_sha256", lambda _: next(hashes))
    elif fault == "bad_pose":
        matcher.reader.observe = lambda frame, at_ms: FaceObservation(
            at_ms, 1, yaw_deg=40, pitch_deg=0, roll_deg=0
        )
    elif fault == "missing_consistency":
        matcher._consistency_threshold = None
    else:
        original = enrolled.session_views

        def corrupted(inp, reader):
            frames, checksum = original(inp, reader)
            frames["left" if fault == "duplicate_views" else "front"] = frames["right"].copy()
            return frames, checksum

        monkeypatch.setattr(enrolled, "session_views", corrupted)
    result = match_enrolled(matcher, inp, template, artifact)
    assert result.gate != "pass" and result.status != "ok"
