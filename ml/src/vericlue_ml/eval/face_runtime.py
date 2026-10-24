"""Check all face backends together on synthetic tensors; never an accuracy benchmark.

No camera, biometric fixture, API, model download or authentication decision.
All backends remain alive together until the checks finish. Run in the isolated
CPU environment described by ml/requirements/face-diagnostic-cpu.txt.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import platform
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from vericlue_ml.eval.report import git_revision
from vericlue_ml.face.fsvfm import (
    CHECKPOINT_FILE,
    MODEL_ID,
    STATS_FILE,
    FsvfmPadDetector,
    face_tensor,
)
from vericlue_ml.face.gend import FaceDeepfakeDetector, to_tensor
from vericlue_ml.face.match import FaceMatchDetector, match_tensor
from vericlue_ml.face.pad import _manifest_entry
from vericlue_ml.presence.landmarks import FaceObservationReader

PACKAGES = (
    "numpy",
    "mediapipe",
    "opencv-contrib-python",
    "onnxruntime",
    "torch",
    "transformers",
    "safetensors",
    "pillow",
)


def runtime_versions() -> dict[str, str | None]:
    """Record installed versions without importing optional native packages."""
    result = {"python": platform.python_version(), "platform": platform.platform()}
    for package in PACKAGES:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def check_backends(
    models_dir: Path, *, progress: Callable[[str], None] | None = None
) -> dict[str, Any]:
    """Exercise MediaPipe, LVFace/SCRFD, GenD and FS-VFM in the same CPU process."""
    reader, matcher = FaceObservationReader(), FaceMatchDetector()
    deepfake, pad = FaceDeepfakeDetector(), FsvfmPadDetector()
    checks = {}

    def record(name, operation):
        if progress:
            progress(f"starting {name}")
        started = perf_counter()
        try:
            checks[name] = {"status": "ok", **operation()}
        except Exception as exc:
            checks[name] = {"status": "error", "exception_type": type(exc).__name__}
        checks[name]["diagnostic_elapsed_ms"] = (perf_counter() - started) * 1000
        if progress:
            progress(f"finished {name}: {checks[name]['status']}")

    def hashes(files):
        return {f"{model}/{file}": _manifest_entry(model, file)["sha256"] for model, file in files}

    def landmarks():
        reader.preload(models_dir=models_dir)
        observation = reader.observe(np.full((240, 320, 3), 127, np.uint8), at_ms=0)
        if observation.face_count != 0:
            raise ValueError("Synthetic constant image must have no face")
        return {
            "face_count": 0,
            "model_sha256": reader.expected_sha256,
            "covers_modules": ["gaze_tracking", "head_turn"],
        }

    def identity():
        matcher.preload(models_dir=models_dir, device="cpu")
        vector = matcher.embedder.embed(match_tensor(np.full((112, 112, 3), 127, np.uint8)))
        if not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1):
            raise ValueError("Invalid identity forward output")
        faces = matcher.finder.find(np.full((240, 320, 3), 127, np.uint8))
        if faces:
            raise ValueError("Synthetic constant image must have no SCRFD face")
        providers = matcher.embedder.session.get_providers()
        if providers != ["CPUExecutionProvider"]:
            raise ValueError("Expected CPU ONNX execution provider")
        return {
            "model_version": matcher.version,
            "finite_output": True,
            "output_shape": list(vector.shape),
            "device": "cpu",
            "providers": providers,
            "model_sha256": hashes(
                [("lvface-b", "LVFace-B_Glint360K.onnx"), ("scrfd-10g", "det_10g.onnx")]
            ),
        }

    def classifier(detector, tensor, files):
        detector.preload(models_dir=models_dir, device="cpu")
        values = detector._classifier.p_fake(tensor[None])
        if len(values) != 1 or not all(math.isfinite(p) and 0 <= p <= 1 for p in values):
            raise ValueError("Invalid classifier forward output")
        backend = detector._classifier
        target = getattr(backend, "_device", getattr(backend, "device", None))
        if str(target) != "cpu":
            raise ValueError("Expected CPU classifier")
        return {
            "model_version": detector.version,
            "finite_output": True,
            "device": "cpu",
            "model_sha256": hashes(files),
        }

    try:
        record("landmarker", landmarks)
        record("face_match", identity)
        blank = np.full((224, 224, 3), 127, np.uint8)
        record(
            "face_deepfake",
            lambda: classifier(
                deepfake,
                to_tensor(blank),
                [("gend-clip-l14", "model.safetensors"), ("clip-vit-large-patch14", "config.json")],
            ),
        )
        record(
            "face_pad",
            lambda: classifier(
                pad, face_tensor(blank), [(MODEL_ID, CHECKPOINT_FILE), (MODEL_ID, STATS_FILE)]
            ),
        )
    finally:
        reader.close()
    return {
        "all_backends_ok": all(row["status"] == "ok" for row in checks.values()),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve().is_relative_to(args.models_dir.resolve()):
        parser.error("--output must be outside the model directory")
    revision = git_revision()
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": revision,
        "dirty": revision.endswith("-dirty"),
        "sample_count": 0,
        "dataset": "synthetic_constant_tensors_not_biometric_evaluation",
        "runtime": runtime_versions(),
        **check_backends(
            args.models_dir, progress=lambda message: print(message, file=sys.stderr, flush=True)
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0 if report["all_backends_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
