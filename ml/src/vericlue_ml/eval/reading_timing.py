"""Internal timing report/CLI. No microphone, ASR substitution or auth decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.nes2net_voice import audio_hash, runtime_versions
from vericlue_ml.eval.report import git_revision
from vericlue_ml.voice.align import ForcedAligner
from vericlue_ml.voice.reading_timing import VERSION, ReadingTimingDetector


def timing_payload(detector, samples: np.ndarray, prompt: str) -> dict:
    """Bind timing to current raw 16 kHz PCM; isolate model/dependency failure."""
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": git_revision(),
        "sample_count": 1,
        "dataset": "local_reading_timing_not_accuracy_evaluation",
        "runtime": runtime_versions(),
        "sample_rate": 16000,
        "input_samples": len(samples),
        "pcm_float32_sha256": hashlib.sha256(
            samples.astype("<f4", copy=False).tobytes()
        ).hexdigest(),
    }
    try:
        result = detector.predict_samples(samples, 16000, prompt=prompt)
        payload.update(detector.provenance())
    except Exception:
        result = ModuleResult(
            module="voice_challenge",
            model_version=VERSION,
            status="error",
            gate="unclear",
            error_code="E_INTERNAL",
            latency_ms=0,
        )
    payload["result"] = result.to_contract()
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--expected-text-file", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if (
        args.output.exists()
        or args.output.resolve() in {args.audio.resolve(), args.expected_text_file.resolve()}
        or args.output.resolve().is_relative_to(args.models_dir.resolve())
    ):
        parser.error("Output must be new, outside models and distinct from inputs")
    if (
        not args.expected_text_file.is_file()
        or not 0 < args.expected_text_file.stat().st_size <= 4096
    ):
        parser.error("Expected text must be a bounded local file")
    prompt = args.expected_text_file.read_text(encoding="utf-8").strip()
    try:
        ForcedAligner.validate_prompt(prompt)
        checksum = audio_hash(args.audio)
    except (OSError, ValueError):
        parser.error("Invalid local audio or expected phrase")
    detector = ReadingTimingDetector(args.models_dir)
    result = detector.predict(DetectorInput(audio=args.audio, metadata={"prompt": prompt}))
    try:
        unchanged = audio_hash(args.audio) == checksum
    except (ValueError, OSError):
        unchanged = False
    if not unchanged:
        result = ModuleResult(
            module=detector.name,
            model_version=detector.version,
            status="error",
            gate="unclear",
            error_code="E_INTEGRITY",
            latency_ms=result.latency_ms,
        )
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": git_revision(),
        "dataset": "local_reading_timing_not_accuracy_evaluation",
        "sample_count": 1,
        "audio_sha256": checksum,
        "prompt_source": "local_text_file_not_server_authenticated",
        "expected_text": prompt,
        "runtime": runtime_versions(),
        **detector.provenance(),
        "result": result.to_contract(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
