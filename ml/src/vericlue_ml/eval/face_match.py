"""Offline LVFace diagnostic for server-resolved reference/front/[left/right] photos."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.eval.report import git_revision
from vericlue_ml.face.match import MODEL_FILE, FaceMatchDetector
from vericlue_ml.face.pad import _verified_weights


def checksum(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--front", type=Path, required=True)
    parser.add_argument("--left", type=Path)
    parser.add_argument("--right", type=Path)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if (args.left is None) != (args.right is None):
        parser.error("--left and --right must be supplied together")
    views = {"front": args.front}
    if args.left is not None:
        views.update(left=args.left, right=args.right)
    artifact = args.calibration or os.environ.get("FACE_MATCH_CALIBRATION")
    detector = FaceMatchDetector(calibration_path=Path(artifact) if artifact else None)
    detector.preload(models_dir=args.models_dir, device=args.device)
    result = detector.predict(
        DetectorInput(
            reference_image=args.reference,
            images=list(views.values()),
            image_roles=list(views),
        )
    )
    model, _ = _verified_weights(args.models_dir, "lvface-b", MODEL_FILE)
    scrfd, _ = _verified_weights(args.models_dir, "scrfd-10g", "det_10g.onnx")
    revision = git_revision()
    import onnxruntime as ort

    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": revision,
        "dirty": revision.endswith("-dirty"),
        "model_sha256": {"lvface-b": checksum(model), "scrfd-10g": checksum(scrfd)},
        "runtime": {
            "onnxruntime": ort.__version__,
            "numpy": importlib.metadata.version("numpy"),
            "providers": detector.embedder.session.get_providers(),
        },
        "sample_count": 1,
        "dataset": "local_diagnostic_not_accuracy_evaluation",
        "inputs_sha256": {
            role: checksum(path) for role, path in {"reference": args.reference, **views}.items()
        },
        "calibration_sha256": checksum(Path(artifact)) if artifact else None,
        "result": result.to_contract(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
