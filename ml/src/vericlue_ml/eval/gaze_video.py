"""Run a local video against a saved server challenge; diagnostic, not a biometric benchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.eval.report import git_revision
from vericlue_ml.presence.gaze import GazeDetector
from vericlue_ml.presence.landmarks import FaceObservationReader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument(
        "--server-response",
        type=Path,
        required=True,
        help="Saved POST /v1/sessions response issued by this server, not client measurements",
    )
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    body = json.loads(args.server_response.read_text(encoding="utf-8"))
    reader = FaceObservationReader()
    detector = GazeDetector(reader)
    reader.preload(models_dir=args.models_dir)
    try:
        result = detector.predict(
            DetectorInput(
                session_id=body["session_id"],
                video=args.video,
                metadata={
                    "challenge_id": body["challenge"]["challenge_id"],
                    "expected_challenge": body["challenge"],
                },
            )
        )
    finally:
        reader.close()
    with args.video.open("rb") as handle:
        checksum = hashlib.file_digest(handle, "sha256").hexdigest()
    revision = git_revision()
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": revision,
        "dirty": revision.endswith("-dirty"),
        "model_sha256": reader.expected_sha256,
        "runtime": {name: importlib.metadata.version(name) for name in ("mediapipe", "numpy")},
        "sample_count": 1,
        "video_sha256": checksum,
        "purpose": "local_diagnostic_not_accuracy_evaluation",
        "result": result.to_contract(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
