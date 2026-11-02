"""Persistent Qwen/CTC/SyncNet worker, local files only; no device or network access."""

import argparse
import contextlib
import hashlib
import json
import sys
from pathlib import Path
from typing import BinaryIO

from vericlue_ml.common.detector import Detector, DetectorInput
from vericlue_ml.common.manual_demo import ManualDemoThresholds
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.runtime.voice_wire import (
    KINDS,
    MAX_REPLY,
    MAX_REQUEST,
    PROTOCOL,
    canonical,
    expected_version,
    source_hashes,
    worker_hello,
    worker_scope,
)


class VoiceModels:
    """Load each model once; timing and SyncNet share one forced aligner."""

    def __init__(
        self, models_dir: Path, *, manual_demo: ManualDemoThresholds | None = None
    ) -> None:
        self.root, self.loaded = models_dir, {}
        self.aligner = None
        self.manual_demo = manual_demo

    def detector(self, kind: str) -> Detector:
        if kind not in self.loaded:
            if kind == "content":
                from vericlue_ml.voice.qwen_asr import QwenASR, QwenVoiceChallengeDetector

                detector = QwenVoiceChallengeDetector(QwenASR(self.root))
            elif kind == "spoof" and self.manual_demo is not None:
                from vericlue_ml.voice.antispoof import AntiDeepfakeDetector

                detector = AntiDeepfakeDetector(self.root, device="cpu")
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

    def preload(self, kinds: tuple[str, ...]) -> None:
        for kind in kinds:
            detector = self.detector(kind)
            expected = expected_version(kind, self.manual_demo)
            if self.manual_demo is not None and kind in {"spoof", "lipsync"}:
                expected = expected.removesuffix(self.manual_demo.version_suffix)
            if detector.version != expected:
                raise ValueError("Wrong preload backend version")
            detector.preload(models_dir=self.root, device="cpu")


def serve(
    source: BinaryIO,
    target: BinaryIO,
    models: VoiceModels,
    media_root: Path,
    *,
    manual_demo: ManualDemoThresholds | None = None,
    warmup_kinds=(),
) -> None:
    """Correlate each answer to request bytes and unchanged media, not just a filename."""
    scope = worker_scope(manual_demo)
    if manual_demo is not None:
        if not warmup_kinds or not set(warmup_kinds) <= KINDS.keys():
            raise ValueError("Manual worker requires explicit model preload")
        with contextlib.redirect_stdout(sys.stderr):
            models.preload(tuple(warmup_kinds))
    target.write(canonical(worker_hello(manual_demo, warmup_kinds)) + b"\n")
    target.flush()
    while line := source.readline(MAX_REQUEST + 1):
        if len(line) > MAX_REQUEST or not line.endswith(b"\n"):
            raise ValueError("Invalid request bounds")
        request = json.loads(line)
        if (
            not isinstance(request, dict)
            or set(request) != {"protocol", "request_id", "kind", "input", "sources"} | scope.keys()
            or any(request.get(key) != value for key, value in scope.items())
            or (manual_demo is not None and request.get("kind") not in warmup_kinds)
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
                if kind == "lipsync" and manual_demo is None:
                    result = result.model_copy(update={"model_version": expected_version(kind)})
                    result.quality.update(
                        audio_offset_ms=inp.metadata.get("audio_offset_ms", 0),
                        hardware_clock_verified=False,
                    )
                if source_hashes(inp, media_root, kind) != request["sources"]:
                    raise ValueError("Changed media")
                if manual_demo is not None and kind in {"spoof", "lipsync"}:
                    result = manual_demo.apply_voice(result)
                elif kind != "content":
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
                    **scope,
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
    parser.add_argument("--manual-policy-json")
    parser.add_argument("--warmup-kinds", default="")
    args = parser.parse_args()
    try:
        policy = (
            ManualDemoThresholds.model_validate_json(args.manual_policy_json)
            if args.manual_policy_json
            else None
        )
        serve(
            sys.stdin.buffer,
            sys.stdout.buffer,
            VoiceModels(args.models_dir, manual_demo=policy),
            args.media_root,
            manual_demo=policy,
            warmup_kinds=tuple(filter(None, args.warmup_kinds.split(","))),
        )
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
