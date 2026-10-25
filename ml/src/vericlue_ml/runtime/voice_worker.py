"""Persistent Qwen/CTC/SyncNet worker, local files only; no device or network access."""

import argparse
import contextlib
import hashlib
import json
import sys
from pathlib import Path
from typing import BinaryIO

from vericlue_ml.common.detector import Detector, DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.runtime.voice_wire import (
    KINDS,
    MAX_REPLY,
    MAX_REQUEST,
    PROTOCOL,
    canonical,
    expected_version,
    source_hashes,
)


class VoiceModels:
    """Load each model once; timing and SyncNet share one forced aligner."""

    def __init__(self, models_dir: Path) -> None:
        self.root, self.loaded = models_dir, {}
        self.aligner = None

    def detector(self, kind: str) -> Detector:
        if kind not in self.loaded:
            if kind == "content":
                from vericlue_ml.voice.qwen_asr import QwenASR, QwenVoiceChallengeDetector

                detector = QwenVoiceChallengeDetector(QwenASR(self.root))
            elif kind == "spoof":
                from vericlue_ml.voice.nes2net_timeline import Nes2NetTimelineDetector

                detector = Nes2NetTimelineDetector(self.root)
            else:
                from vericlue_ml.voice.align import ForcedAligner

                if self.aligner is None:
                    self.aligner = ForcedAligner(self.root)
                if kind == "timing":
                    from vericlue_ml.voice.reading_timing import ReadingTimingDetector

                    detector = ReadingTimingDetector(self.root, aligner=self.aligner)
                else:
                    from vericlue_ml.voice.syncnet import SyncNetDetector

                    detector = SyncNetDetector(self.root, aligner=self.aligner)
            self.loaded[kind] = detector
        return self.loaded[kind]


def serve(source: BinaryIO, target: BinaryIO, models: VoiceModels, media_root: Path) -> None:
    """Correlate each answer to request bytes and unchanged media, not just a filename."""
    target.write(canonical({"protocol": PROTOCOL, "ready": True}) + b"\n")
    target.flush()
    while line := source.readline(MAX_REQUEST + 1):
        if len(line) > MAX_REQUEST or not line.endswith(b"\n"):
            raise ValueError("Invalid request bounds")
        request = json.loads(line)
        if (
            not isinstance(request, dict)
            or set(request) != {"protocol", "request_id", "kind", "input", "sources"}
            or request["protocol"] != PROTOCOL
            or request["kind"] not in KINDS
            or not isinstance(request["request_id"], str)
            or len(request["request_id"]) != 32
        ):
            raise ValueError("Invalid worker request")
        kind = request["kind"]
        inp = DetectorInput.model_validate(request["input"])
        checksum = hashlib.sha256(line[:-1]).hexdigest()
        with contextlib.redirect_stdout(sys.stderr):
            try:
                if source_hashes(inp, media_root, kind) != request["sources"]:
                    raise ValueError("Changed media")
                detector = models.detector(kind)
                if kind == "content" and "voice_match_config" in inp.metadata:
                    from vericlue_ml.router.config import VoiceConfig

                    detector.match_config = VoiceConfig.model_validate(
                        inp.metadata["voice_match_config"]
                    )
                result = detector.predict(inp)
                if kind == "lipsync":
                    result = result.model_copy(update={"model_version": expected_version(kind)})
                    result.quality.update(
                        audio_offset_ms=inp.metadata.get("audio_offset_ms", 0),
                        hardware_clock_verified=False,
                    )
                if source_hashes(inp, media_root, kind) != request["sources"]:
                    raise ValueError("Changed media")
                if kind != "content":
                    result = result.model_copy(
                        update={
                            "status": "degraded" if result.status == "ok" else result.status,
                            "gate": "unclear",
                            "prob_attack": None,
                        }
                    )
            except Exception:
                result = ModuleResult(
                    module=KINDS[kind],
                    model_version="unavailable",
                    status="error",
                    gate="unclear",
                    error_code="E_INTERNAL",
                    latency_ms=0,
                )
        reply = (
            canonical(
                {
                    "protocol": PROTOCOL,
                    "request_id": request["request_id"],
                    "request_sha256": checksum,
                    "sources": request["sources"],
                    "result": result.to_contract(),
                }
            )
            + b"\n"
        )
        if len(reply) > MAX_REPLY:
            raise ValueError("Reply too large")
        target.write(reply)
        target.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        serve(sys.stdin.buffer, sys.stdout.buffer, VoiceModels(args.models_dir), args.media_root)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
