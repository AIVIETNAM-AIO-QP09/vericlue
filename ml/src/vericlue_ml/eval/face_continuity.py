"""Offline continuity diagnostic; trusted local clips/CCCD/challenge, never an API verdict."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.eval.face_match import checksum
from vericlue_ml.eval.report import git_revision
from vericlue_ml.face.continuity import FaceContinuityDetector
from vericlue_ml.face.video_match import VideoFaceMatchDetector
from vericlue_ml.presence.landmarks import FaceObservationReader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "face-video",
        "voice-video",
        "audio",
        "reference-card",
        "server-response",
        "models-dir",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--voice-challenge-id", required=True)
    parser.add_argument("--audio-offset-ms", type=int, default=0)
    parser.add_argument("--face-calibration", type=Path)
    parser.add_argument("--continuity-calibration", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    args = parser.parse_args(argv)
    if args.face_calibration is None and os.environ.get("FACE_MATCH_CALIBRATION"):
        args.face_calibration = Path(os.environ["FACE_MATCH_CALIBRATION"])
    sources = {
        name: getattr(args, name)
        for name in (
            "face_video",
            "voice_video",
            "audio",
            "reference_card",
            "server_response",
            "face_calibration",
            "continuity_calibration",
        )
        if getattr(args, name) is not None
    }
    if args.output.resolve() in {p.resolve() for p in sources.values()}:
        parser.error("Output must not overwrite an input or calibration artifact")
    body = json.loads(args.server_response.read_text(encoding="utf-8"))
    reader = FaceObservationReader()
    matcher = VideoFaceMatchDetector(reader=reader, calibration_path=args.face_calibration)
    detector = FaceContinuityDetector(matcher, reader, calibration_path=args.continuity_calibration)
    try:
        matcher.preload(models_dir=args.models_dir, device=args.device)
        detector.preload(models_dir=args.models_dir, device=args.device)
        metadata = {
            "challenge_id": body["challenge"]["challenge_id"],
            "expected_challenge": body["challenge"],
        }
        reference = matcher.predict(
            DetectorInput(
                session_id=body["session_id"],
                video=args.face_video,
                reference_image=args.reference_card,
                metadata=metadata,
            )
        )
        result = detector.predict(
            DetectorInput(
                session_id=body["session_id"],
                reference_video=args.face_video,
                video=args.voice_video,
                audio=args.audio,
                metadata={
                    **metadata,
                    "face_reference_result": reference.to_contract(),
                    "voice_challenge_id": args.voice_challenge_id,
                    "expected_voice_challenge_id": args.voice_challenge_id,
                    "audio_offset_ms": args.audio_offset_ms,
                },
            )
        )
    finally:
        reader.close()
    payload = {
        "commit": git_revision(),
        "created_at": datetime.now(UTC).isoformat(),
        "sample_count": 1,
        "dataset": "local_diagnostic_not_accuracy_evaluation",
        "source_sha256": {name: checksum(path) for name, path in sources.items()},
        "face_match": reference.to_contract(),
        "face_continuity": result.to_contract(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return int(reference.status == "error" or result.status == "error")


if __name__ == "__main__":
    raise SystemExit(main())
