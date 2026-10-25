"""Diagnostic report provenance and input protection, without model weights."""

import json

import pytest

from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval import face_continuity as cli
from vericlue_ml.face.continuity import FACE_VOICE_VERSION
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION


def arguments(tmp_path):
    params = []
    for name in ("face-video", "voice-video", "audio", "reference-card", "server-response"):
        path = tmp_path / (name + ".txt")
        path.write_text(
            json.dumps({"session_id": "ses_cli", "challenge": {"challenge_id": "ch_cli"}})
        )
        params.extend(["--" + name, str(path)])
    return [
        *params,
        "--models-dir",
        str(tmp_path),
        "--voice-challenge-id",
        "vc_cli",
        "--output",
        str(tmp_path / "report.json"),
    ]


def test_report_records_commit_versions_source_hashes_and_count(monkeypatch, tmp_path):
    closed = []

    class Reader:
        def close(self):
            closed.append(True)

    class Matcher:
        def __init__(self, *args, **kwargs):
            pass

        def preload(self, **kwargs):
            pass

        def predict(self, inp):
            return ModuleResult(
                module="face_match",
                model_version=VIDEO_MATCH_VERSION,
                status="degraded",
                gate="unclear",
                latency_ms=0,
            )

    class Continuity(Matcher):
        def predict(self, inp):
            assert inp.reference_video.name == "face-video.txt"
            return ModuleResult(
                module="face_continuity",
                model_version=FACE_VOICE_VERSION,
                status="degraded",
                gate="unclear",
                score=0.2,
                latency_ms=0,
            )

    monkeypatch.setattr(cli, "FaceObservationReader", Reader)
    monkeypatch.setattr(cli, "VideoFaceMatchDetector", Matcher)
    monkeypatch.setattr(cli, "FaceContinuityDetector", Continuity)
    monkeypatch.setattr(cli, "git_revision", lambda: "a" * 40)
    assert cli.main(arguments(tmp_path)) == 0
    result = json.loads((tmp_path / "report.json").read_text())
    assert result["commit"] == "a" * 40 and result["sample_count"] == 1
    assert result["face_continuity"]["model_version"] == FACE_VOICE_VERSION
    assert len(result["source_sha256"]) == 5
    assert result["dataset"] == "local_diagnostic_not_accuracy_evaluation"
    assert closed == [True] and "embedding" not in json.dumps(result)


def test_output_must_not_overwrite_a_source(tmp_path):
    args = arguments(tmp_path)
    args[-1] = args[1]
    original = (tmp_path / "face-video.txt").read_bytes()
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    assert (tmp_path / "face-video.txt").read_bytes() == original
