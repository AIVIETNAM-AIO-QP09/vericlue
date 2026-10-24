"""Offline NES2Net first-four-seconds raw diagnostic; no mic or authentication decision."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.report import git_revision
from vericlue_ml.voice.nes2net import MAX_BYTES, Nes2NetDetector


def runtime_versions() -> dict[str, str | None]:
    """Report missing optional libraries too, so failure artifacts can still be written."""
    result = {}
    for name in ("transformers", "torch", "numpy", "soundfile"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def audio_hash(path: Path) -> str:
    """Only bounded local files; no remote URLs or unbounded hashing."""
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("Expected bounded local audio")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--models-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.resolve() == args.audio.resolve() or args.output.resolve().is_relative_to(
        args.models_dir.resolve()
    ):
        parser.error("Output cannot overwrite audio or models")
    if args.output.exists():
        parser.error("Output must be a new file")
    checksum = audio_hash(args.audio)
    detector = Nes2NetDetector(args.models_dir)
    result = detector.predict(DetectorInput(audio=args.audio))
    try:
        unchanged = audio_hash(args.audio) == checksum
    except (ValueError, OSError):
        unchanged = False
    if not unchanged:
        result = ModuleResult(
            module="voice_spoof",
            model_version=detector.version,
            status="error",
            gate="unclear",
            error_code="E_INTEGRITY",
            latency_ms=result.latency_ms,
        )
    backend = detector.backend
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": git_revision(),
        "model_version": detector.version,
        "model_revision": backend.config["revision"],
        "expected_model_hashes": {backend.config["checkpoint"]: backend.config["sha256"]},
        "verified_model_hashes": backend.model_hashes,
        "load_report": backend.load_report,
        "model_loaded": backend._model is not None,
        "dataset": "local_nes2net_diagnostic_not_accuracy_evaluation",
        "sample_count": 1,
        "audio_sha256": checksum,
        "protocol": "first_64000_samples_repeat_if_short_no_normalization_no_trim",
        "frontend_parity_verified": False,
        "calibrated": False,
        "runtime": runtime_versions(),
        "result": result.to_contract(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
