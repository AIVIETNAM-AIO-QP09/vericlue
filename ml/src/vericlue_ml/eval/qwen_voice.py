"""Offline Qwen content diagnostic on one local clip; no microphone or API decision."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ErrorCode, Gate, Module, ModuleResult, Status
from vericlue_ml.eval.report import git_revision
from vericlue_ml.presence.challenge import expected_dynamic
from vericlue_ml.voice.qwen_asr import MAX_AUDIO_BYTES, QwenASR, QwenVoiceChallengeDetector


def audio_sha256(path: Path) -> str:
    """Bound local file hashing; URL strings are not decoded or fetched."""
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_AUDIO_BYTES:
        raise ValueError("Audio must be a bounded local file")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--expected-text-file", type=Path)
    source.add_argument("--server-response", type=Path)
    args = parser.parse_args(argv)
    expected_path = args.server_response or args.expected_text_file
    if args.output.resolve() in {
        args.audio.resolve(),
        expected_path.resolve(),
    } or args.output.resolve().is_relative_to(args.models_dir.resolve()):
        parser.error("Output must not overwrite audio, expected text, server response or models")
    if not expected_path.is_file() or not 0 < expected_path.stat().st_size <= 1024 * 1024:
        parser.error("Expected text/server response must be a bounded local file")
    inp = DetectorInput(audio=args.audio)
    if args.server_response:
        body = json.loads(args.server_response.read_text(encoding="utf-8"))
        inp.session_id = body["session_id"]
        inp.metadata = {
            "expected_challenge": body["challenge"],
            "challenge_id": body["challenge"]["challenge_id"],
        }
        dynamic = expected_dynamic(inp)
        inp.metadata["prompt"] = dynamic["voice_prompt"]
        prompt_source = "saved_server_response_not_signature_verified_first_attempt_only"
    else:
        inp.metadata["prompt"] = args.expected_text_file.read_text(encoding="utf-8").strip()
        prompt_source = "local_text_file_not_server_authenticated"
    prompt = inp.metadata.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1024:
        parser.error("Expected phrase must contain 1–1024 characters")
    checksum = audio_sha256(args.audio)
    asr = QwenASR(args.models_dir)
    result = QwenVoiceChallengeDetector(asr).predict(inp)
    if audio_sha256(args.audio) != checksum:
        result = ModuleResult(
            module=Module.VOICE_CHALLENGE,
            model_version=asr.version,
            status=Status.ERROR,
            gate=Gate.UNCLEAR,
            error_code=ErrorCode.E_INTEGRITY,
            latency_ms=result.latency_ms,
        )
    config = asr.config
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "commit": git_revision(),
        "model_version": asr.version,
        "model_revision": config["revision"],
        "expected_model_hashes": config["sha256"],
        "verified_model_hashes": asr.model_hashes,
        "model_loaded": asr._model is not None,
        "dataset": "local_content_diagnostic_not_accuracy_evaluation",
        "sample_count": 1,
        "audio_sha256": checksum,
        "prompt_source": prompt_source,
        "runtime": {
            name: importlib.metadata.version(name)
            for name in ("transformers", "torch", "numpy", "soundfile", "webrtcvad-wheels")
        },
        "result": result.to_contract(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
