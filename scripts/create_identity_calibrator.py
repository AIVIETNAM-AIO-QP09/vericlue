"""Create explicit identity artifacts for MVP without loading models or data (ADR-0012)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from vericlue_ml.common.calibration import CalibrationError, CalibrationStore, identity
from vericlue_ml.common.result import Module

ROOT = Path(__file__).resolve().parents[1]


def run(module: Module, model_version: str, output_dir: Path) -> Path:
    """Use an exact verified detector version; never replace an already fitted artifact."""
    store = CalibrationStore(output_dir)
    path = store.path(module, model_version)
    if path.exists() and store.load(module, model_version).method != "identity":
        raise CalibrationError("Refusing to replace a fitted calibrator with identity")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    artifact = identity(module=module, model_version=model_version, commit=commit)
    return store.save(artifact)


def main() -> None:
    """Require the runtime version, not the generic pre-preload constructor name."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module", required=True, choices=["face_pad", "face_deepfake", "voice_spoof"]
    )
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ml/configs/calibrators")
    args = parser.parse_args()
    print(run(Module(args.module), args.model_version, args.output_dir))


if __name__ == "__main__":
    main()
