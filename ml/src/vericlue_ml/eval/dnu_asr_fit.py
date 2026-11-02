"""Predeclared DNU calib_fit content comparison; never install or tune a policy.

One fixed clip per speaker, one backend load. References reach only the existing
matching rules and syllable-count budget. No phone, heldout audio/metadata, ASR
context, or authentication decisions. Reports omit transcripts and private IDs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import wave
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path, PurePosixPath
from platform import python_version
from time import perf_counter

import yaml

from vericlue_ml.eval.diagnostic_output import check_diagnostic_output
from vericlue_ml.eval.report import git_revision
from vericlue_ml.eval.voice_challenge import _predict
from vericlue_ml.router.config import load_config

PROTOCOL = "app03-dnu-asr-fit-v1"
SEED = PROTOCOL + ":"
REPOSITORY = "TrangLe2108/DNU-ViSpeech"
REVISION = "33b2a469901cb71b243403254d3cfef25170526c"
DATASET = "DNU-ViSpeech-bonafide-only-v1"
PHOWHISPER_REVISION = "a86b604c346caf7148c37512eafe783a16420adb"
QWEN_REVISION = "7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c"
QWEN17_REVISION = "bcd2b5b7f32b480ab5790554cfa8347f246a14f3"
VERSIONS = {
    "qwen": f"qwen3-asr-06b@{QWEN_REVISION}+cpu-fp32-content-v2-assistant-prefix",
    "qwen17": f"qwen3-asr-17b@{QWEN17_REVISION}+cpu-fp32-content-v2-assistant-prefix",
    "phowhisper": f"phowhisper-small@{PHOWHISPER_REVISION}+voice04-v2",
}
ROOT = Path(__file__).resolve().parents[4]


def _require(condition: object) -> None:
    if not condition:
        raise ValueError("Invalid fit-only protocol or source integrity")


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _inside(root: Path, relative: str) -> Path:
    _require(
        isinstance(relative, str) and relative and ":" not in relative and "\\" not in relative
    )
    parts = PurePosixPath(relative)
    _require(not parts.is_absolute() and ".." not in parts.parts)
    path = (root / relative).resolve()
    _require(path.is_relative_to(root.resolve()) and path.is_file())
    return path


@dataclass(frozen=True)
class FitSample:
    audio: Path
    reference: str
    checksum: str
    speaker_index: int


@dataclass(frozen=True)
class FitPlan:
    samples: tuple[FitSample, ...]
    receipts: tuple[tuple[Path, str], ...]
    protocol_sha256: str

    def unchanged(self) -> bool:
        """Recheck source receipts after collection without opening heldout files."""
        return all(_sha(path) == expected for path, expected in self.receipts)


def load_protocol(protocol: Path, expected_sha256: str) -> FitPlan:
    """Validate the operator-frozen selection and exact train transcript crosswalk."""
    _require(_sha(protocol) == expected_sha256 and len(expected_sha256) == 64)
    body = json.loads(protocol.read_text(encoding="utf-8"))
    _require(body["protocol"] == PROTOCOL and body["selection_seed"] == SEED)
    _require(body["dataset"] == DATASET and body["source_revision"] == REVISION)
    _require(
        body["train_manifest_rows"] == 360 and body["sample_count"] == body["subject_count"] == 18
    )
    _require(body["labels_not_model_context"] is True and body["fixed_thresholds"] is True)
    _require(
        body["heldout_audio_or_metadata_read"] is False
        and body["fit_or_threshold_install"] is False
    )
    data = Path(body["data_root"]).resolve()
    receipts = [(protocol.resolve(), expected_sha256)]
    for relative, key in (
        ("manifest.json", "manifest_sha256"),
        ("source/data/train/metadata.csv", "train_metadata_sha256"),
        ("source/LICENSE", "license_sha256"),
        ("source/PUBLIC_RELEASE_APPROVAL.md", "approval_sha256"),
    ):
        source = _inside(data, relative)
        _require(_sha(source) == body[key])
        receipts.append((source, body[key]))
    _require("CC BY-NC 4.0" in (data / "source/LICENSE").read_text(encoding="utf-8"))
    _require(bool((data / "source/PUBLIC_RELEASE_APPROVAL.md").read_text(encoding="utf-8").strip()))
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    _require(manifest["dataset"] == DATASET and manifest["schema_version"] == 1)
    # Only the publisher's train metadata is opened. Other manifest entries are
    # filtered before their media or transcript fields are used.
    fit = [row for row in manifest["samples"] if row.get("split") == "calib_fit"]
    _require(len(fit) == 360)
    with (data / "source/data/train/metadata.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require(
            reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames)
        )
        metadata = list(reader)
    by_id = {row["audio_id"]: row for row in metadata}
    _require(len(by_id) == len(metadata))
    groups, references, seen_ids, seen_paths = {}, {}, set(), set()
    for row in fit:
        sample_id = row["sample_id"]
        _require(isinstance(sample_id, str) and sample_id.startswith("DNU:"))
        source = by_id[sample_id.removeprefix("DNU:")]
        _require(row["source_dataset"] == REPOSITORY and row["source_revision"] == REVISION)
        _require(row["label"] == 0 and row["attack_type"] == "bonafide")
        _require(row["subject_ids"] == ["DNU:" + source["speaker_id"]])
        _require(row["audio"] == "DNU-ViSpeech/data/train/" + source["file_name"])
        _require(row["audio_sha256"] == source["checksum_sha256"])
        _require(
            source["split"] == "train"
            and source["review_status"] == "accepted"
            and source["qc_status"] == "passed"
        )
        _require(int(source["sample_rate"]) == 16000 and int(source["num_channels"]) == 1)
        _require(isinstance(source["text_normalized"], str) and source["text_normalized"].strip())
        audio = _inside(data, row["audio"])
        _require(sample_id not in seen_ids and audio not in seen_paths)
        seen_ids.add(sample_id)
        seen_paths.add(audio)
        _require(_sha(audio) == row["audio_sha256"])
        with wave.open(str(audio)) as wav:
            duration = wav.getnframes() / wav.getframerate()
            _require(
                wav.getframerate() == 16000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
            )
        _require(abs(duration - float(source["duration"])) <= 0.05)
        if 1 <= duration <= 30:
            groups.setdefault(row["subject_ids"][0], []).append(row)
            references[sample_id] = source["text_normalized"]
    _require(len(groups) == 18)
    chosen = [
        min(rows, key=lambda r: hashlib.sha256((SEED + r["sample_id"]).encode()).hexdigest())
        for _, rows in sorted(groups.items())
    ]
    _require(chosen == body["private_samples"])
    samples = tuple(
        FitSample(
            _inside(data, row["audio"]),
            references[row["sample_id"]],
            row["audio_sha256"],
            index + 1,
        )
        for index, row in enumerate(chosen)
    )
    return FitPlan(samples, tuple(receipts), expected_sha256)


def phowhisper_manifest_entry() -> dict:
    """Read the repository's already approved model manifest; never update it."""
    manifest = yaml.safe_load((ROOT / "models/manifest.yaml").read_text(encoding="utf-8"))
    return next(row for row in manifest["models"] if row["id"] == "phowhisper")


def verify_models(backend: str, models_dir: Path) -> dict:
    """Hash the candidate weights before loading; no Torch/model imports for verification."""
    if backend == "qwen17":
        from vericlue_ml.eval.qwen17_asr import Qwen17ASR

        asr = Qwen17ASR(models_dir)
        asr._verify()
        return {"verified": True, "revision": QWEN17_REVISION, "file_sha256": asr.model_hashes}
    if backend == "qwen":
        from vericlue_ml.voice.qwen_asr import QwenASR

        asr = QwenASR(models_dir)
        _require(
            asr.config
            == yaml.safe_load((ROOT / "ml/configs/qwen3_asr.yaml").read_text(encoding="utf-8"))
        )
        asr._verify()
        return {"verified": True, "revision": QWEN_REVISION, "file_sha256": asr.model_hashes}
    _require(backend == "phowhisper")
    entry = phowhisper_manifest_entry()
    _require(
        entry["source"]["revision"] == PHOWHISPER_REVISION
        and entry["license"] == "BSD-3-Clause"
        and entry["license_status"] == "verified"
    )
    hashes = {}
    for row in entry["files"]:
        path = _inside(models_dir, "phowhisper/" + row["path"])
        actual = _sha(path)
        _require(path.stat().st_size == row["size_bytes"] and actual == row["sha256"])
        _require(row.get("upstream_sha256") in (None, actual))
        hashes[row["path"]] = actual
    return {"verified": True, "revision": PHOWHISPER_REVISION, "file_sha256": hashes}


def _detector(backend: str, models_dir: Path):
    if backend == "qwen17":
        from vericlue_ml.eval.qwen17_asr import Qwen17ASR
        from vericlue_ml.voice.qwen_asr import QwenVoiceChallengeDetector

        return QwenVoiceChallengeDetector(Qwen17ASR(models_dir))
    if backend == "qwen":
        from vericlue_ml.voice.qwen_asr import QwenASR, QwenVoiceChallengeDetector

        asr = QwenASR(models_dir)
        _require(
            asr.config
            == yaml.safe_load((ROOT / "ml/configs/qwen3_asr.yaml").read_text(encoding="utf-8"))
        )
        return QwenVoiceChallengeDetector(asr)
    from vericlue_ml.voice.asr import PhoWhisperASR
    from vericlue_ml.voice.challenge import VoiceChallengeDetector

    asr = PhoWhisperASR(models_dir, device="cpu")
    _require(asr.model_dir.resolve() == (models_dir / "phowhisper").resolve() and asr.vad_mode == 1)
    return VoiceChallengeDetector(asr)


def runtime_provenance() -> dict:
    """Read installed distribution versions without importing Torch or model code."""
    result = {"python": python_version()}
    for name in (
        "torch",
        "transformers",
        "tokenizers",
        "safetensors",
        "numpy",
        "scipy",
        "soundfile",
        "webrtcvad-wheels",
        "jiwer",
        "rapidfuzz",
    ):
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def _source_provenance() -> dict[str, str]:
    files = (
        "ml/configs/models.yaml",
        "ml/configs/qwen3_asr.yaml",
        "ml/configs/thresholds.yaml",
        "ml/src/vericlue_ml/voice/asr.py",
        "ml/src/vericlue_ml/voice/challenge.py",
        "ml/src/vericlue_ml/voice/qwen_asr.py",
        "ml/src/vericlue_ml/eval/qwen17_asr.py",
        "ml/src/vericlue_ml/eval/voice_challenge.py",
    )
    return {name: _sha(ROOT / name) for name in files}


def _measurement(result: dict, index: int) -> dict:
    status, gate = result.get("status", "error"), result.get("gate", "unclear")
    quality = result.get("quality") or {}
    wer, similarity = quality.get("syllable_error_rate"), quality.get("unaccented_similarity")
    valid = (
        status == "ok"
        and gate in {"pass", "fail"}
        and not (gate == "pass" and result.get("error_code"))
        and all(
            type(value) in (int, float) and math.isfinite(value) and value >= 0
            for value in (wer, similarity)
        )
        and similarity <= 1
    )
    latency = result.get("latency_ms", 0)
    if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
        latency = 0.0
    if status == "ok" and not valid:
        status, gate = "error", "unclear"
    return {
        "speaker_index": index,
        "sample_count": 1,
        "status": status,
        "gate": gate,
        "error_code": result.get("error_code") or ("E_INTERNAL" if status == "error" else None),
        "nonpass": status != "ok" or gate != "pass",
        "wer": float(wer) if valid else None,
        "unaccented_similarity": float(similarity) if valid else None,
        "latency_ms": float(latency),
    }


def _summary(rows: list[dict]) -> dict:
    usable = [row for row in rows if row["wer"] is not None]
    return {
        "sample_count": len(rows),
        "speaker_count": len(rows),
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "error_code_counts": dict(Counter(row["error_code"] for row in rows if row["error_code"])),
        "nonpass_count": sum(row["nonpass"] for row in rows),
        "nonpass_denominator": len(rows),
        "wer_available_count": len(usable),
        "wer_unavailable_count": len(rows) - len(usable),
        "macro_speaker_wer_available": sum(row["wer"] for row in usable) / len(usable)
        if usable
        else None,
        "macro_unaccented_similarity_available": sum(row["unaccented_similarity"] for row in usable)
        / len(usable)
        if usable
        else None,
        "latency_total_ms": sum(row["latency_ms"] for row in rows),
        "latency_max_ms": max(row["latency_ms"] for row in rows),
        "errors_are_nonpass": True,
        "missing_wer_is_not_zero": True,
    }


def collect(
    protocol: Path,
    protocol_sha256: str,
    backend: str,
    models_dir: Path,
    output: Path,
    *,
    detector=None,
) -> dict:
    """Collect one fixed backend; error rows remain in every operational denominator."""
    _require(backend in VERSIONS)
    target = check_diagnostic_output(output, protected=[protocol], models_dir=models_dir)
    plan = load_protocol(protocol, protocol_sha256)
    _require(not target.is_relative_to(plan.receipts[1][0].parent))
    fixed = load_config(ROOT / "ml/configs/thresholds.yaml").voice
    code_hash = _sha(Path(__file__))
    sources = _source_provenance()
    versions = runtime_provenance()
    startup = perf_counter()
    verification, ready = {"verified": False}, False
    try:
        verification = verify_models(backend, models_dir)
        runtime = detector if detector is not None else _detector(backend, models_dir)
        _require(detector is not None or runtime.version == VERSIONS[backend])
        runtime.match_config = fixed
        runtime.preload(models_dir=models_dir, device="cpu")
        ready = True
    except Exception:
        runtime = detector
    preload_ms = (perf_counter() - startup) * 1000
    rows = []
    for sample in plan.samples:
        result = {"status": "error", "gate": "unclear", "error_code": "E_INTERNAL"}
        if ready:
            try:
                if _sha(sample.audio) != sample.checksum:
                    result["error_code"] = "E_INTEGRITY"
                else:
                    result = _predict(runtime, sample.audio, sample.reference)
                    if _sha(sample.audio) != sample.checksum:
                        result = {"status": "error", "gate": "unclear", "error_code": "E_INTEGRITY"}
            except OSError:
                result = {"status": "error", "gate": "unclear", "error_code": "E_INTEGRITY"}
        rows.append(_measurement(result, sample.speaker_index))
    try:
        unchanged = (
            plan.unchanged()
            and _sha(Path(__file__)) == code_hash
            and _source_provenance() == sources
            and runtime_provenance() == versions
            and load_config(ROOT / "ml/configs/thresholds.yaml").voice == fixed
        )
    except OSError:
        unchanged = False
    if not unchanged:
        rows = [
            _measurement({"status": "error", "error_code": "E_INTEGRITY"}, sample.speaker_index)
            for sample in plan.samples
        ]
    report = {
        "protocol": PROTOCOL,
        "source_commit": git_revision(),
        "implementation_sha256": code_hash,
        "source_and_config_sha256": sources,
        "runtime": versions,
        "protocol_sha256": protocol_sha256,
        "source_revision": REVISION,
        "dataset": DATASET,
        "scope": "calib_fit-only bonafide content diagnostic; not accuracy on phone, spoof calibration, or authentication readiness",
        "backend": backend,
        "model_version": getattr(runtime, "version", VERSIONS[backend]),
        "model_verification": verification,
        "backend_preloaded": ready,
        "preload_ms": preload_ms,
        "source_unchanged": unchanged,
        "speaker_aggregates": rows,
        "overall": _summary(rows),
        "fixed_matching_rules": {
            "max_syllable_wer": fixed.max_syllable_wer,
            "min_unaccented_similarity": fixed.min_unaccented_similarity,
        },
        "no_reference_text_in_asr_context": True,
        "heldout_audio_or_metadata_read": False,
        "phone_recordings_used": False,
        "threshold_or_deployment_artifact_installed": False,
        "transcripts_or_private_ids_in_report": False,
    }
    check_diagnostic_output(
        output, protected=[path for path, _ in plan.receipts], models_dir=models_dir
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report


def main(argv: list[str] | None = None) -> int:
    """Check a frozen selection or run a candidate; stdout contains aggregate results only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--backend", choices=VERSIONS)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.check_only and any(
        value is None for value in (args.backend, args.models_dir, args.output)
    ):
        parser.error("Collection requires backend, models-dir and a new private output")
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            if args.check_only:
                plan = load_protocol(args.protocol, args.protocol_sha256)
                summary = {
                    "protocol_valid": True,
                    "sample_count": len(plan.samples),
                    "speaker_count": len(plan.samples),
                    "inference_performed": False,
                }
                code = 0
            else:
                report = collect(
                    args.protocol, args.protocol_sha256, args.backend, args.models_dir, args.output
                )
                summary = {
                    "backend": args.backend,
                    "source_commit": report["source_commit"],
                    "overall": report["overall"],
                    "transcripts_or_private_ids_in_stdout": False,
                }
                code = (
                    1
                    if not report["source_unchanged"] or report["overall"]["wer_unavailable_count"]
                    else 0
                )
    except Exception:
        print(json.dumps({"completed": False, "protocol_or_source_invalid": True}))
        return 1
    print(json.dumps(summary))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
