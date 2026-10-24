"""Persistent offline NES2Net worker: bounded stdin PCM, stdout JSON only, no devices."""

from __future__ import annotations

import argparse
import contextlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from vericlue_ml.eval.voice_wire import PROTOCOL, encode_reply, read_request


def serve(source: BinaryIO, target: BinaryIO, detector) -> None:
    """One request at a time; reuse detector, wipe the main PCM buffer after each take."""
    from vericlue_ml.eval.nes2net_voice import runtime_versions
    from vericlue_ml.eval.report import git_revision

    while (frame := read_request(source)) is not None:
        header, samples = frame
        try:
            # Third-party libraries may print progress; keep protocol stdout clean.
            with contextlib.redirect_stdout(sys.stderr):
                result = detector.predict_samples(samples, 16000)
            backend = detector.backend
            payload = {
                "protocol": PROTOCOL,
                "created_at": datetime.now(UTC).isoformat(),
                "request_id": header["request_id"],
                "pcm_float32_sha256": header["sha256"],
                "commit": git_revision(),
                "model_version": detector.version,
                "model_revision": backend.config["revision"],
                "expected_model_hashes": {backend.config["checkpoint"]: backend.config["sha256"]},
                "verified_model_hashes": backend.model_hashes,
                "model_loaded": backend._model is not None,
                "load_report": backend.load_report,
                "runtime": runtime_versions(),
                "sample_count": 1,
                "frontend_parity_verified": False,
                "calibrated": False,
                "resampled_sample_rate": 16000,
                "received_samples": len(samples),
                "result": result.to_contract(),
            }
            target.write(encode_reply(payload))
            target.flush()
        finally:
            samples.fill(0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    source, target = sys.stdin.buffer, sys.stdout.buffer
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from vericlue_ml.voice.nes2net import Nes2NetDetector

            detector = Nes2NetDetector(args.models_dir)
        serve(source, target, detector)
    except Exception:
        # Do not print PCM, paths or a misleading protocol response after bad framing.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
