"""Diagnostic chain: server challenge -> video head poses -> in-memory views -> LVFace.

Saved challenge JSON is trusted local input here, not a public HTTP request.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.eval.face_match import checksum
from vericlue_ml.eval.report import git_revision
from vericlue_ml.face.fsvfm import CHECKPOINT_FILE, MODEL_ID, FsvfmPadDetector
from vericlue_ml.face.gend import FaceDeepfakeDetector
from vericlue_ml.face.match import FaceMatchDetector
from vericlue_ml.face.pad import _manifest_entry
from vericlue_ml.presence.landmarks import FaceObservationReader
from vericlue_ml.presence.video_identity import match_video_views


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--server-response", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument(
        "--with-gend",
        action="store_true",
        help="Also score the selected views with GenD; requires the gend extra",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--with-pad",
        action="store_true",
        help="Also score views with FS-VFM-L (FP32); requires face + gend extras",
    )
    args = parser.parse_args(argv)
    artifact = args.calibration or os.environ.get("FACE_MATCH_CALIBRATION")
    inputs = [args.video, args.reference, args.server_response]
    if artifact:
        inputs.append(Path(artifact))
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("--output must not overwrite an input or calibration file")
    body = json.loads(args.server_response.read_text(encoding="utf-8"))
    reader = FaceObservationReader()
    matcher = FaceMatchDetector(calibration_path=args.calibration)
    deepfake = FaceDeepfakeDetector() if args.with_gend else None
    pad = FsvfmPadDetector() if args.with_pad else None
    try:
        result = match_video_views(
            DetectorInput(
                session_id=body["session_id"],
                video=args.video,
                reference_image=args.reference,
                metadata={
                    "challenge_id": body["challenge"]["challenge_id"],
                    "expected_challenge": body["challenge"],
                },
            ),
            reader=reader,
            matcher=matcher,
            deepfake=deepfake,
            pad=pad,
            models_dir=args.models_dir,
            device=args.device,
        )
    finally:
        reader.close()
    revision = git_revision()
    face_loaded = matcher.embedder.session is not None
    gend_loaded = deepfake is not None and deepfake._classifier is not None
    pad_loaded = pad is not None and pad._classifier is not None
    runtime = {name: importlib.metadata.version(name) for name in ("numpy", "mediapipe")}
    if face_loaded:
        import onnxruntime as ort

        runtime.update(
            onnxruntime=ort.__version__, providers=matcher.embedder.session.get_providers()
        )
    if gend_loaded or pad_loaded:
        import torch

        runtime["torch"] = torch.__version__
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": revision,
        "dirty": revision.endswith("-dirty"),
        "sample_count": 1,
        "dataset": "local_diagnostic_not_accuracy_evaluation",
        "runtime": runtime,
        "video_sha256": checksum(args.video),
        "reference_sha256": checksum(args.reference),
        "challenge_file_sha256": checksum(args.server_response),
        "landmarker_sha256": reader.expected_sha256,
        "face_match_model_loaded": face_loaded,
        "gend_requested": args.with_gend,
        "gend_model_loaded": gend_loaded,
        "pad_requested": args.with_pad,
        "pad_model_loaded": pad_loaded,
        "pad_model_sha256": _manifest_entry(MODEL_ID, CHECKPOINT_FILE)["sha256"]
        if pad_loaded
        else None,
        "gend_model_sha256": _manifest_entry("gend-clip-l14", "model.safetensors")["sha256"]
        if gend_loaded
        else None,
        "face_match_model_sha256": {
            "lvface-b": _manifest_entry("lvface-b", "LVFace-B_Glint360K.onnx")["sha256"],
            "scrfd-10g": _manifest_entry("scrfd-10g", "det_10g.onnx")["sha256"],
        }
        if face_loaded
        else None,
        "calibration_sha256": checksum(Path(artifact))
        if artifact and Path(artifact).is_file()
        else None,
        "results": result.to_contract(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return (
        1
        if any(
            r is not None and r.status == "error"
            for r in (result.head_turn, result.face_match, result.face_deepfake, result.face_pad)
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
