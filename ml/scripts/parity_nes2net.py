#!/usr/bin/env python3
"""VOICE-08/VOICE-09 numerical parity harness: NES2Net-X Fairseq vs Transformers.

Compares the converted VeriClue `Nes2NetBackend` (HuggingFace `Wav2Vec2Model` +
`Nes2NetHead`, CPU float32) against the pinned upstream Fairseq reference
(`Liu-Tianchi/Nes2Net_ASVspoof_ITW` @ `c9fe1177f44040f002cb40def928332d2e261f1e`,
`model_scripts/wav2vec2_Nes2Net_X.py`) on identical 64,000-sample (4.0 s @ 16 kHz)
float32 windows prepared by `vericlue_ml.voice.nes2net.prepare_samples`.

If no Fairseq reference runtime (`--reference-python`) is supplied, the script
runs the converted side, verifies preprocessing and checkpoint mapping
provenance, writes a JSON report with `status="UNVERIFIED"`, and exits with
code 2. It never fabricates reference logits or marks parity as verified
without executing the real Fairseq frontend.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from vericlue_ml.voice import nes2net

UPSTREAM_COMMIT = nes2net.REVISION
UPSTREAM_MODEL_REL = Path("model_scripts/wav2vec2_Nes2Net_X.py")
UPSTREAM_MODEL_SHA256 = "8a81756688e026243b40c0a8733e2d122401322c74cb32add8046f9bb60bc75f"
MIN_PARITY_CLIPS = 32
LOGIT_DIFF_TOLERANCE = 1e-4
MARGIN_DIFF_TOLERANCE = 1e-4

REFERENCE_WORKER_CODE = r"""
import json
import sys
from pathlib import Path

upstream_dir = Path(sys.argv[1]).resolve()
xlsr_path = Path(sys.argv[2]).resolve()
checkpoint_path = Path(sys.argv[3]).resolve()
windows_path = Path(sys.argv[4]).resolve()
output_path = Path(sys.argv[5]).resolve()

sys.path.insert(0, str(upstream_dir))
import fairseq
import fairseq.checkpoint_utils as cu
from fairseq.tasks.audio_pretraining import AudioPretrainingConfig, AudioPretrainingTask
import numpy as np
import torch

orig_load = cu.load_model_ensemble_and_task

def patched_load(filenames, arg_overrides=None, **kwargs):
    # The public XLS-R checkpoint contains obsolete dataset/training task fields
    # (multiple_train_files/eval_wer/...). Fairseq 0.12.2 cannot merge them.
    # This task only constructs the checkpoint's unchanged model graph; no dataset
    # or task inference/preprocessing is used. Both sides receive identical PCM.
    kwargs.setdefault("task", AudioPretrainingTask(AudioPretrainingConfig()))
    return orig_load([str(xlsr_path)], arg_overrides=arg_overrides, **kwargs)

cu.load_model_ensemble_and_task = patched_load
from model_scripts.wav2vec2_Nes2Net_X import wav2vec2_Nes2Net_no_Res_w_allT as UpstreamModel

class Args:
    n_output_logits = 2
    Nes_ratio = [8, 8]
    dilation = 2
    pool_func = "mean"
    SE_ratio = [1]

torch.set_num_threads(int(sys.argv[6]))
torch.manual_seed(0)
device = "cpu"
model = UpstreamModel(Args(), device).to(device="cpu", dtype=torch.float32)
try:
    state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
except TypeError:
    state = torch.load(checkpoint_path, map_location="cpu")
if isinstance(state, dict) and "state_dict" in state and isinstance(state["state_dict"], dict):
    state = state["state_dict"]
cleaned = {(k[7:] if k.startswith("module.") else k): v for k, v in state.items()}
missing, unexpected = model.load_state_dict(cleaned, strict=False)
if missing or unexpected:
    raise RuntimeError(f"Upstream state_dict mismatch: missing={missing}, unexpected={unexpected}")
model = model.to(device="cpu", dtype=torch.float32).eval()

payload = np.load(windows_path, allow_pickle=False)
windows = payload["windows"]
logits_out = []
with torch.inference_mode():
    for idx in range(windows.shape[0]):
        wav = torch.from_numpy(np.ascontiguousarray(windows[idx], dtype=np.float32)).unsqueeze(0)
        out = model(wav)
        if model.training or model.ssl_model.model.training:
            raise RuntimeError("Upstream model entered train() mode during reference evaluation")
        row = np.asarray(out.squeeze(0).detach().cpu().numpy(), dtype=np.float64).reshape(-1)
        if row.shape != (2,) or not np.isfinite(row).all():
            raise RuntimeError(f"Invalid upstream logits at window {idx}: {row}")
        logits_out.append([float(row[0]), float(row[1])])

report = {
    "python_version": sys.version.split()[0],
    "torch_version": torch.__version__,
    "fairseq_version": fairseq.__version__,
    "window_logits": logits_out,
}
output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _sha256_array(values: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(values, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _synthetic_waveforms(count: int = 4) -> list[tuple[str, np.ndarray]]:
    """Deterministic multi-tone float32 signals for converted-side smoke checks."""
    items: list[tuple[str, np.ndarray]] = []
    lengths = (16000, 32000, 64000, 80000)
    for idx in range(count):
        length = lengths[idx % len(lengths)]
        t = np.arange(length, dtype=np.float32) / np.float32(nes2net.SAMPLE_RATE)
        f0 = 110.0 + 25.0 * idx
        phase = 2.0 * np.pi * (f0 * t + 2.5 * np.sin(2.0 * np.pi * 1.5 * t))
        signal = (
            0.16 * np.sin(phase) + 0.07 * np.sin(2.0 * phase + 0.3) + 0.04 * np.cos(3.0 * phase)
        ).astype(np.float32)
        items.append((f"synthetic_{idx}_{length}", signal))
    return items


def _load_audio_list(path: Path) -> list[Path]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        raise ValueError(f"Audio list is empty: {path}")
    paths: list[Path] = []
    for raw in lines:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = (path.parent / candidate).resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Missing audio file in list: {candidate}")
        paths.append(candidate)
    return paths


def prepare_window_records(
    *,
    audio_files: list[Path] | None = None,
    synthetic_smoke: bool = False,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """Prepare 64,000-sample windows and record preprocessing invariants."""
    if bool(audio_files) == bool(synthetic_smoke):
        raise ValueError("Specify exactly one of audio_files or synthetic_smoke=True")

    records: list[dict[str, Any]] = []
    windows: list[np.ndarray] = []

    if synthetic_smoke:
        for name, samples in _synthetic_waveforms():
            # Bypass VAD for synthetic tone smoke while testing exact pad/crop rules.
            if len(samples) < nes2net.WINDOW_SAMPLES:
                reps = int(np.ceil(nes2net.WINDOW_SAMPLES / len(samples)))
                window = np.tile(samples, reps)[: nes2net.WINDOW_SAMPLES].astype(
                    np.float32, copy=True
                )
            else:
                window = np.array(samples[: nes2net.WINDOW_SAMPLES], dtype=np.float32, copy=True)
            records.append(
                {
                    "clip_id": name,
                    "source_samples": int(len(samples)),
                    "source_sha256": _sha256_array(samples),
                    "window_samples": int(len(window)),
                    "window_sha256": _sha256_array(window),
                    "repeated_to_four_seconds": bool(len(samples) < nes2net.WINDOW_SAMPLES),
                    "truncated": bool(len(samples) > nes2net.WINDOW_SAMPLES),
                    "synthetic": True,
                }
            )
            windows.append(window)
    else:
        assert audio_files is not None
        for audio_path in audio_files:
            raw = nes2net.Nes2NetDetector._read_file(audio_path)
            window = nes2net.prepare_samples(raw, nes2net.SAMPLE_RATE)
            records.append(
                {
                    "clip_id": audio_path.name,
                    "audio_sha256": _sha256_file(audio_path),
                    "source_samples": int(len(raw)),
                    "source_sha256": _sha256_array(raw),
                    "window_samples": int(len(window)),
                    "window_sha256": _sha256_array(window),
                    "repeated_to_four_seconds": bool(len(raw) < nes2net.WINDOW_SAMPLES),
                    "truncated": bool(len(raw) > nes2net.WINDOW_SAMPLES),
                    "synthetic": False,
                }
            )
            windows.append(window)

    stacked = np.stack(windows, axis=0).astype(np.float32, copy=False)
    return records, stacked


def run_converted_windows(backend: Any, windows: np.ndarray) -> list[dict[str, Any]]:
    """Run converted Nes2NetBackend on prepared 64,000-sample windows."""
    if windows.ndim != 2 or windows.shape[1] != nes2net.WINDOW_SAMPLES:
        raise ValueError(f"Expected (N, {nes2net.WINDOW_SAMPLES}) windows, got {windows.shape}")
    results: list[dict[str, Any]] = []
    for idx in range(windows.shape[0]):
        logits = np.asarray(backend.logits(windows[idx]), dtype=np.float64).reshape(-1)
        if logits.shape != (2,) or not np.isfinite(logits).all():
            raise ValueError(f"Invalid converted logits at index {idx}: {logits}")
        margin = float(logits[0] - logits[1])
        results.append(
            {
                "window_index": idx,
                "logits": [float(logits[0]), float(logits[1])],
                "margin_score": margin,
            }
        )
    return results


def compare_logits(
    converted: list[dict[str, Any]],
    reference_logits: list[list[float]],
    *,
    synthetic: bool = False,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare converted vs Fairseq reference logits and margins on identical windows."""
    if len(converted) != len(reference_logits) or not converted:
        raise ValueError("Converted and reference window counts must match and be non-empty")

    conv_arr = np.asarray([row["logits"] for row in converted], dtype=np.float64)
    ref_arr = np.asarray(reference_logits, dtype=np.float64)
    if conv_arr.shape != ref_arr.shape or conv_arr.shape[1] != 2:
        raise ValueError(f"Logit shape mismatch: {conv_arr.shape} vs {ref_arr.shape}")
    if not np.isfinite(conv_arr).all() or not np.isfinite(ref_arr).all():
        raise ValueError("Non-finite logits in parity comparison")

    logit_diffs = np.abs(conv_arr - ref_arr)
    conv_margins = conv_arr[:, 0] - conv_arr[:, 1]
    ref_margins = ref_arr[:, 0] - ref_arr[:, 1]
    margin_diffs = np.abs(conv_margins - ref_margins)

    # Sign agreement on non-zero margins (spoof > bonafide vs spoof <= bonafide).
    conv_sign = conv_margins >= 0.0
    ref_sign = ref_margins >= 0.0
    sign_agreement = float(np.mean(conv_sign == ref_sign))

    max_logit_diff = float(np.max(logit_diffs))
    mean_logit_diff = float(np.mean(logit_diffs))
    max_margin_diff = float(np.max(margin_diffs))
    mean_margin_diff = float(np.mean(margin_diffs))

    numerical_ok = (
        max_logit_diff <= LOGIT_DIFF_TOLERANCE
        and max_margin_diff <= MARGIN_DIFF_TOLERANCE
        and sign_agreement == 1.0
    )
    diversity = check_sample_diversity(records) if records is not None else None
    independent_count = (
        diversity["independent_sample_count"] if diversity is not None else len(converted)
    )
    no_duplicates = diversity["all_unique"] if diversity is not None else True
    enough_clips = (not synthetic) and independent_count >= MIN_PARITY_CLIPS and no_duplicates
    status = "PASS" if (numerical_ok and enough_clips) else "UNVERIFIED" if numerical_ok else "FAIL"
    out = {
        "status": status,
        "window_count": len(converted),
        "independent_sample_count": independent_count,
        "synthetic": synthetic,
        "min_required_clips": MIN_PARITY_CLIPS,
        "max_abs_logit_diff": max_logit_diff,
        "mean_abs_logit_diff": mean_logit_diff,
        "max_abs_margin_diff": max_margin_diff,
        "mean_abs_margin_diff": mean_margin_diff,
        "sign_agreement": sign_agreement,
        "tolerances": {
            "max_abs_logit_diff": LOGIT_DIFF_TOLERANCE,
            "max_abs_margin_diff": MARGIN_DIFF_TOLERANCE,
            "sign_agreement": 1.0,
        },
    }
    if diversity is not None:
        out["diversity"] = diversity
    return out


def check_sample_diversity(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify independence/diversity of prepared windows so duplicates cannot inflate sample count."""
    unique_window_hashes = {
        str(rec["window_sha256"]) for rec in records if rec.get("window_sha256")
    }
    unique_source_hashes = {
        str(rec["source_sha256"]) for rec in records if rec.get("source_sha256")
    }
    unique_audio_hashes = {str(rec["audio_sha256"]) for rec in records if rec.get("audio_sha256")}
    total = len(records)
    unique_windows = len(unique_window_hashes)
    unique_sources = len(unique_source_hashes)
    unique_audios = len(unique_audio_hashes) if unique_audio_hashes else unique_sources
    duplicate_window_count = max(0, total - unique_windows)
    duplicate_source_count = max(0, total - unique_sources)
    independent_count = min(unique_windows, unique_sources, unique_audios)
    return {
        "total_records": total,
        "unique_window_count": unique_windows,
        "unique_source_count": unique_sources,
        "unique_audio_file_count": unique_audios,
        "duplicate_window_count": duplicate_window_count,
        "duplicate_source_count": duplicate_source_count,
        "independent_sample_count": independent_count,
        "all_unique": bool(total > 0 and independent_count == total),
    }


def _run_reference_python(
    reference_python: Path,
    upstream_dir: Path,
    xlsr_checkpoint: Path,
    nes2net_checkpoint: Path,
    windows: np.ndarray,
    cpu_threads: int = 4,
) -> dict[str, Any]:
    upstream_script = (upstream_dir / UPSTREAM_MODEL_REL).resolve()
    if not upstream_script.is_file():
        raise FileNotFoundError(f"Missing upstream model script: {upstream_script}")
    if _sha256_file(upstream_script) != UPSTREAM_MODEL_SHA256:
        raise ValueError(f"Upstream script SHA-256 mismatch: {upstream_script}")
    if not xlsr_checkpoint.is_file():
        raise FileNotFoundError(f"Missing Fairseq XLS-R checkpoint: {xlsr_checkpoint}")

    with tempfile.TemporaryDirectory(prefix="nes2net-parity-") as tmp:
        tmp_dir = Path(tmp)
        windows_path = tmp_dir / "windows.npz"
        output_path = tmp_dir / "reference.json"
        worker_path = tmp_dir / "worker.py"
        np.savez(windows_path, windows=windows)
        worker_path.write_text(REFERENCE_WORKER_CODE, encoding="utf-8")
        child_env = os.environ.copy()
        for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            child_env.pop(name, None)
        child_env.update(
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            CUDA_VISIBLE_DEVICES="",
            PYTHONDONTWRITEBYTECODE="1",
            OMP_NUM_THREADS="1",
        )
        subprocess.run(
            [
                str(reference_python),
                str(worker_path),
                str(upstream_dir.resolve()),
                str(xlsr_checkpoint.resolve()),
                str(nes2net_checkpoint.resolve()),
                str(windows_path),
                str(output_path),
                str(cpu_threads),
            ],
            env=child_env,
            check=True,
            timeout=600,
        )
        return json.loads(output_path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path(os.environ.get("MODELS_DIR", "./models")),
        help="Root directory containing nes2net-x-xlsr/checkpoint.pth",
    )
    parser.add_argument(
        "--audio-list",
        type=Path,
        default=None,
        help="Newline-separated list of 16 kHz mono WAV files (>= 32 for PASS)",
    )
    parser.add_argument(
        "--synthetic-smoke",
        action="store_true",
        help="Run deterministic synthetic 16 kHz waveforms (status stays UNVERIFIED)",
    )
    parser.add_argument(
        "--reference-python",
        type=Path,
        default=None,
        help="Path to Python 3.10 interpreter with fairseq==0.12.2 installed",
    )
    parser.add_argument(
        "--upstream-dir",
        type=Path,
        default=None,
        help="Path to Liu-Tianchi/Nes2Net_ASVspoof_ITW @ c9fe1177f44040f002cb40def928332d2e261f1e",
    )
    parser.add_argument(
        "--xlsr-checkpoint",
        type=Path,
        default=None,
        help="Path to Fairseq xlsr2_300m.pt required by upstream SSLModel",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New JSON file path to write the parity report",
    )
    parser.add_argument(
        "--source-commit",
        help="Verified 40-hex source commit when Windows git worktree metadata is unreadable in WSL",
    )
    args = parser.parse_args(argv)

    if args.source_commit is not None and (
        len(args.source_commit) != 40
        or any(c not in "0123456789abcdef" for c in args.source_commit)
    ):
        parser.error("--source-commit must be a lowercase 40-hex Git commit")

    if args.output.exists():
        parser.error(f"Output file already exists: {args.output}")
    if bool(args.audio_list) == bool(args.synthetic_smoke):
        parser.error("Provide exactly one of --audio-list or --synthetic-smoke")

    audio_files = _load_audio_list(args.audio_list) if args.audio_list else None
    records, windows = prepare_window_records(
        audio_files=audio_files,
        synthetic_smoke=args.synthetic_smoke,
    )
    windows_sha256 = _sha256_array(windows)

    backend = nes2net.Nes2NetBackend(args.models_dir)
    backend.preload()
    converted = run_converted_windows(backend, windows)

    diversity = check_sample_diversity(records)
    report: dict[str, Any] = {
        "task": "VOICE-08/VOICE-09",
        "model_version": nes2net.VERSION,
        "upstream_revision": UPSTREAM_COMMIT,
        "commit": args.source_commit or _git_commit(),
        "script_sha256": _sha256_file(Path(__file__)),
        "date": datetime.now(UTC).isoformat(),
        "windows_sha256": windows_sha256,
        "window_count": len(records),
        "independent_sample_count": diversity["independent_sample_count"],
        "diversity": diversity,
        "synthetic_smoke": bool(args.synthetic_smoke),
        "converted_runtime": {
            "python_version": sys.version.split()[0],
            "torch_version": _package_version("torch"),
            "transformers_version": _package_version("transformers"),
            "numpy_version": np.__version__,
            "cpu_threads": backend.config.get("cpu_threads", 4),
            "verified_model_hashes": dict(backend.model_hashes),
            "load_report": dict(backend.load_report),
        },
        "windows": [{**rec, **conv} for rec, conv in zip(records, converted, strict=True)],
    }

    if args.reference_python is not None:
        if args.upstream_dir is None or args.xlsr_checkpoint is None:
            parser.error("--reference-python requires --upstream-dir and --xlsr-checkpoint")
        checkpoint_path = (
            args.models_dir.resolve()
            / str(backend.config["model_subdir"])
            / str(backend.config["checkpoint"])
        )
        ref_out = _run_reference_python(
            args.reference_python,
            args.upstream_dir,
            args.xlsr_checkpoint,
            checkpoint_path,
            windows,
            cpu_threads=backend.config.get("cpu_threads", 4),
        )
        comparison = compare_logits(
            converted,
            ref_out["window_logits"],
            synthetic=bool(args.synthetic_smoke),
            records=records,
        )
        report["reference_runtime"] = {
            "python_version": ref_out["python_version"],
            "torch_version": ref_out["torch_version"],
            "fairseq_version": ref_out["fairseq_version"],
            "cpu_threads": backend.config.get("cpu_threads", 4),
        }
        report["reference_window_logits"] = ref_out["window_logits"]
        report["comparison"] = comparison
        report["status"] = comparison["status"]
    else:
        report["reference_runtime"] = None
        report["comparison"] = None
        report["status"] = "UNVERIFIED"
        report["unverified_reason"] = (
            "Fairseq reference runtime (--reference-python) not provided; "
            "converted-side preprocessing and checkpoint load verified only."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["status"] == "PASS":
        return 0
    if report["status"] == "UNVERIFIED":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
