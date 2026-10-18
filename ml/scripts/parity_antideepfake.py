"""Compare converted CPU logits with pinned upstream Fairseq in an external Linux env.

No network, installation, calibration or checkpoint mutation occurs here. The reference
worker imports the user's local upstream checkout; no upstream implementation is copied.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

UPSTREAM_COMMIT = "0dea622bde8f064c8ee5a557f2598643123fc6b6"
WEIGHTS_REVISION = "7928e119e09f616b2ce698892e00ca22dbaa40bf"
WEIGHTS_SHA256 = "9bd5d9785bf72f91dfca8508651354946c4b307921cb358505e1b94035102224"
TOLERANCE = 1e-4


def digest(path: Path) -> str:
    """Hash the actual local bytes without loading audio/model files into memory."""
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            checksum.update(chunk)
    return checksum.hexdigest()


def environment() -> dict:
    """Record package/runtime versions, never environment variables or credentials."""
    packages = {}
    for name in ("torch", "torchaudio", "transformers", "fairseq", "safetensors", "numpy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }


def git_state(root: Path) -> dict:
    """Require a Git checkout so source provenance cannot be silently invented."""
    git = ["git", "-c", f"safe.directory={root.resolve()}"]
    commit = subprocess.check_output(
        [*git, "rev-parse", "HEAD"], cwd=root, text=True, encoding="utf-8", errors="replace"
    ).strip()
    dirty = bool(
        subprocess.check_output(
            [*git, "status", "--porcelain"], cwd=root, text=True, encoding="utf-8", errors="replace"
        )
    )
    return {"commit": commit, "dirty": dirty}


def reference_worker(argv: list[str]) -> int:
    """Private subprocess entry: the only code path which imports Fairseq."""
    parser = argparse.ArgumentParser(description="Local pinned Fairseq reference worker")
    parser.add_argument("--upstream-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 10) or platform.system() != "Linux":
        raise RuntimeError("Reference requires a separate Linux Python 3.10 environment")
    source = git_state(args.upstream_dir)
    if source != {"commit": UPSTREAM_COMMIT, "dirty": False}:
        raise RuntimeError("Reference checkout must match the pinned commit and be clean")
    if importlib.metadata.version("fairseq") != "0.12.2":
        raise RuntimeError("Reference requires fairseq==0.12.2")
    import numpy as np
    import torch
    from safetensors.torch import load_file

    # Import the audited BSD-3-Clause implementation from the external checkout only.
    sys.path.insert(0, str(args.upstream_dir.resolve()))
    from models.W2V import Model

    torch.set_num_threads(1)
    torch.manual_seed(0)
    model = Model("mms_300m").to("cpu").eval()
    incompatible = model.load_state_dict(load_file(str(args.checkpoint), device="cpu"), strict=True)
    logits = []
    with np.load(args.windows, allow_pickle=False) as windows, torch.inference_mode():
        for name in sorted(windows.files):
            audio = np.asarray(windows[name], dtype=np.float32)
            output = model(torch.from_numpy(audio.copy()).unsqueeze(0))
            values = output.detach().cpu().numpy()
            if values.shape != (1, 2) or not np.isfinite(values).all():
                raise RuntimeError("Reference produced invalid binary logits")
            logits.append({"window_id": name, "logits": values[0].tolist()})
    report = {
        "environment": environment(),
        "source": source,
        "missing_keys": list(incompatible.missing_keys),
        "unexpected_keys": list(incompatible.unexpected_keys),
        "source_files": {
            name: digest(args.upstream_dir / name)
            for name in ("models/W2V.py", "models/W2V_configs.py", "LICENSE-CODE")
        },
        "windows": logits,
    }
    args.result.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def run_comparison(args, report: dict) -> int:
    """Normalize once in the wrapper; feed byte-identical float32 windows to both backends."""
    if not args.reference_python and not args.reference_docker_image:
        report["reason"] = (
            "External Python or Docker reference was not provided; parity is UNVERIFIED"
        )
        return 2
    if len(args.audio) != 4 or (args.reference_python and not args.upstream_dir):
        report["reason"] = "Exactly four --audio files and a reference source checkout are required"
        return 2
    if args.upstream_dir:
        upstream = git_state(args.upstream_dir)
        report["upstream_source"] = upstream
        if upstream != {"commit": UPSTREAM_COMMIT, "dirty": False}:
            report["reason"] = "Upstream checkout is not the exact clean pinned revision"
            return 2
    elif args.reference_docker_image:
        report["upstream_source_location"] = (
            "Pinned clean checkout inside reference image at /reference; validated by worker"
        )
    checkpoint = args.models_dir / "antideepfake-mms300m" / "model.safetensors"
    report["checkpoint"] = {"path": str(checkpoint.resolve()), "sha256": digest(checkpoint)}
    if report["checkpoint"]["sha256"] != WEIGHTS_SHA256:
        report.update(status="FAIL", reason="Local checkpoint does not match the pinned SHA-256")
        return 1
    import numpy as np
    import torch

    from vericlue_ml.voice.antispoof import (
        TorchAntiDeepfakeBackend,
        make_windows,
        normalized_window,
        preprocess_audio,
    )

    torch.set_num_threads(1)
    torch.manual_seed(0)
    backend = TorchAntiDeepfakeBackend(models_dir=args.models_dir, device="cpu")
    backend.preload()
    torch.set_num_threads(1)
    load_report = backend.load_report
    if not isinstance(load_report, dict):
        load_report = vars(load_report)
    report["converted_load"] = load_report
    if load_report.get("missing_keys") or load_report.get("unexpected_keys"):
        report.update(status="FAIL", reason="Converted runtime has missing or unexpected keys")
        return 1
    if "missing_keys" not in load_report or "unexpected_keys" not in load_report:
        report["reason"] = "Converted backend must expose explicit missing_keys/unexpected_keys"
        return 2
    with tempfile.TemporaryDirectory(prefix="vericlue-antideepfake-parity-") as temporary:
        folder = Path(temporary)
        windows, sample_metadata, converted = {}, [], []
        for sample_index, path in enumerate(args.audio):
            audio, original_seconds = preprocess_audio(path)
            sample = {
                "path": str(path.resolve()),
                "sha256": digest(path),
                "original_duration_seconds": original_seconds,
                "trimmed_samples_16khz": len(audio),
                "windows": [],
            }
            for window_index, (start, end, raw_window) in enumerate(make_windows(audio)):
                identifier = f"sample_{sample_index:04d}_window_{window_index:06d}"
                normalized = np.ascontiguousarray(normalized_window(raw_window), dtype=np.float32)
                if normalized.ndim != 1 or not normalized.size or not np.isfinite(normalized).all():
                    raise ValueError("Preprocessing produced an invalid normalized window")
                windows[identifier] = normalized
                values = np.asarray(backend.logits(normalized), dtype=np.float64)
                if values.shape != (2,) or not np.isfinite(values).all():
                    raise ValueError("Converted backend produced invalid binary logits")
                converted.append({"window_id": identifier, "logits": values.tolist()})
                sample["windows"].append(
                    {
                        "window_id": identifier,
                        "start_seconds": start,
                        "end_seconds": end,
                        "normalized_samples": len(normalized),
                        "normalized_sha256": hashlib.sha256(normalized.tobytes()).hexdigest(),
                    }
                )
            if not sample["windows"]:
                raise ValueError("Each sample must yield at least one eligible inference window")
            sample_metadata.append(sample)
        report["samples"] = sample_metadata
        np.savez(folder / "windows.npz", **windows)
        reference_path = folder / "reference.json"
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
        worker_args = [
            "--_reference-worker",
            "--upstream-dir",
            str(args.upstream_dir.resolve()) if args.upstream_dir else "/reference",
            "--checkpoint",
            str(checkpoint.resolve()),
            "--windows",
            str(folder / "windows.npz"),
            "--result",
            str(reference_path),
        ]
        if args.reference_docker_image:
            image_id = subprocess.check_output(
                ["docker", "image", "inspect", "--format", "{{.Id}}", args.reference_docker_image],
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            ).strip()
            if not image_id.startswith("sha256:"):
                raise ValueError("Docker reference image did not resolve to an immutable image ID")
            report["reference_container"] = {
                "requested_image": args.reference_docker_image,
                "image_id": image_id,
            }
            command = [
                "docker",
                "run",
                "--rm",
                "--pull=never",
                "--network=none",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--env",
                "HF_HUB_OFFLINE=1",
                "--env",
                "TRANSFORMERS_OFFLINE=1",
                "--env",
                "CUDA_VISIBLE_DEVICES=",
                "--env",
                "OMP_NUM_THREADS=1",
                "--mount",
                f"type=bind,source={checkpoint.parent.resolve()},target=/checkpoint,readonly",
                "--mount",
                f"type=bind,source={folder.resolve()},target=/parity",
                "--mount",
                f"type=bind,source={Path(__file__).resolve().parent},target=/scripts,readonly",
                "--entrypoint",
                "python",
                image_id,
                "/scripts/parity_antideepfake.py",
                "--_reference-worker",
                "--upstream-dir",
                "/reference",
                "--checkpoint",
                "/checkpoint/model.safetensors",
                "--windows",
                "/parity/windows.npz",
                "--result",
                "/parity/reference.json",
            ]
            if args.upstream_dir:
                command[2:2] = [
                    "--mount",
                    f"type=bind,source={args.upstream_dir.resolve()},target=/reference,readonly",
                ]
        else:
            command = [str(args.reference_python), str(Path(__file__).resolve()), *worker_args]
        result = subprocess.run(
            command,
            env=child_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        if result.returncode != 0 or not reference_path.is_file():
            report["reason"] = "External reference could not complete; parity remains UNVERIFIED"
            report["reference_exit_code"] = result.returncode
            report["reference_stderr_tail"] = result.stderr[-4000:]
            return 2
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        report["reference"] = reference
        report["upstream_source"] = reference["source"]
        reference_values = {row["window_id"]: row["logits"] for row in reference["windows"]}
        if set(reference_values) != set(windows):
            raise ValueError("Reference did not evaluate exactly the supplied normalized windows")
        comparisons = []
        for row in converted:
            expected = np.asarray(reference_values[row["window_id"]], dtype=np.float64)
            actual = np.asarray(row["logits"], dtype=np.float64)
            if expected.shape != (2,) or not np.isfinite(expected).all():
                raise ValueError("Reference logits are invalid")
            error = float(np.max(np.abs(actual - expected)))
            comparisons.append(
                {
                    "window_id": row["window_id"],
                    "converted_logits": actual.tolist(),
                    "reference_logits": expected.tolist(),
                    "max_abs_error": error,
                }
            )
        maximum = max(row["max_abs_error"] for row in comparisons)
        report.update(
            windows=comparisons,
            max_abs_error=maximum,
            status="PASS" if maximum <= TOLERANCE else "FAIL",
        )
        report["reason"] = (
            "All logits within tolerance"
            if maximum <= TOLERANCE
            else "Logit difference exceeds 1e-4"
        )
        return 0 if maximum <= TOLERANCE else 1


def main(argv: list[str] | None = None) -> int:
    """Write evidence even when parity cannot be checked; never claim unexecuted parity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, action="append", default=[])
    parser.add_argument("--models-dir", type=Path, default=Path(os.getenv("MODELS_DIR", "models")))
    reference = parser.add_mutually_exclusive_group()
    reference.add_argument("--reference-python", type=Path)
    reference.add_argument(
        "--reference-docker-image", help="Prebuilt local Linux Python 3.10/Fairseq image"
    )
    parser.add_argument("--upstream-dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = {path.resolve() for path in args.audio}
    protected.add((args.models_dir / "antideepfake-mms300m" / "model.safetensors").resolve())
    if args.report.resolve() in protected or args.report.resolve().is_relative_to(
        args.models_dir.resolve()
    ):
        parser.error("Report cannot overwrite model artifacts or audio inputs")
    report = {
        "status": "UNVERIFIED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10 worker
        "weights_revision": WEIGHTS_REVISION,
        "upstream_commit": UPSTREAM_COMMIT,
        "tolerance_max_abs_logits": TOLERANCE,
        "score_order": ["fake", "real"],
        "environment": environment(),
        "scope": "Raw logits on the same normalized windows; no fitting or threshold selection",
    }
    try:
        report["wrapper_source"] = git_state(Path(__file__).resolve().parents[2])
        code = run_comparison(args, report)
    except Exception as exc:
        report["reason"] = f"Parity execution could not complete: {type(exc).__name__}"
        code = 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(args.report),
                "reason": report.get("reason"),
            },
            ensure_ascii=False,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(
        reference_worker(sys.argv[2:]) if sys.argv[1:2] == ["--_reference-worker"] else main()
    )
