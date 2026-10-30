"""FACE-06: isolated FP32 export and reproducible network-only ONNX comparison.

Run export, Torch benchmark and ORT benchmark in separate processes to release
each framework's allocators. Never changes registry, thresholds or live API flags.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import os
import platform
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from vericlue_ml.eval.onnx_metrics import (
    ATTACK_INDICES,
    MODEL_IDS,
    SHAPE,
    compare_outputs,
    inside,
    latency_summary,
    sha256,
    synthetic_inputs,
    write_json,
)


def _versions() -> dict:
    names = (
        "torch",
        "onnx",
        "onnxscript",
        "onnxruntime",
        "onnxruntime-gpu",
        "numpy",
        "transformers",
    )
    versions = {}
    for name in names:
        with contextlib.suppress(importlib.metadata.PackageNotFoundError):
            versions[name] = importlib.metadata.version(name)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": versions,
    }


def _provenance() -> dict:
    root = Path(__file__).resolve().parents[4]
    files = [
        Path(__file__),
        Path(__file__).with_name("onnx_metrics.py"),
        Path(__file__).with_name("onnx_networks.py"),
    ]
    files += [
        root / "ml/src/vericlue_ml/face" / name
        for name in ("fsvfm.py", "fsvfm_network.py", "gend.py")
    ]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, text=True
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", True
    return {
        "source_commit": commit,
        "source_dirty": dirty,
        "source_sha256": {str(p.relative_to(root)).replace("\\", "/"): sha256(p) for p in files},
    }


class _Memory:
    def __init__(self) -> None:
        import psutil

        self.process = psutil.Process()
        self.start = self.process.memory_info().rss
        self.peak = self.start
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while not self.stop.wait(0.02):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()
        self.peak = max(self.peak, self.process.memory_info().rss)

    def result(self) -> dict:
        info = self.process.memory_info()
        return {
            "rss_start_mib": self.start / 2**20,
            "rss_peak_sampled_mib": self.peak / 2**20,
            "rss_end_mib": info.rss / 2**20,
            "sampling_interval_ms": 20,
        }


def _gpu_used() -> float | None:
    """Whole-device snapshot, including other processes; not a process VRAM peak."""
    try:
        raw = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits", "--id=0"],
            timeout=10,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return float(raw.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _torch_settings(device: str, threads: int) -> None:
    import torch

    torch.set_num_threads(threads)
    if device == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("CUDA is unavailable; refusing a CPU fallback")
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False


def _torch_run(network, images: np.ndarray, device: str) -> dict:
    import torch

    with torch.inference_mode():
        tensor = torch.from_numpy(images).to(device)
        logits, probabilities = network(tensor)
        return {"logits": logits.cpu().numpy(), "probabilities": probabilities.cpu().numpy()}


def _collect(run, images: np.ndarray) -> dict:
    rows = [run(frame[None]) for frame in images]
    return {
        name: np.concatenate([row[name] for row in rows]) for name in ("logits", "probabilities")
    }


def _read_outputs(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in ("logits", "probabilities")}


def _bundle(directory: Path) -> tuple[dict, np.ndarray]:
    metadata = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
    if (
        metadata["format"] != 1
        or metadata["model"] not in MODEL_IDS
        or tuple(metadata["input_shape"]) != SHAPE
        or metadata["dtype"] != "float32"
    ):
        raise ValueError("Unsupported ONNX bundle")
    for name, expected in metadata["files"].items():
        if sha256(inside(directory, name)) != expected:
            raise ValueError("Bundle integrity mismatch")
    images = np.load(directory / "inputs.npy", allow_pickle=False)
    if (
        images.dtype != np.float32
        or images.shape != (metadata["samples"], *SHAPE[1:])
        or not np.isfinite(images).all()
    ):
        raise ValueError("Invalid validation inputs")
    return metadata, images


def export(args) -> None:
    import onnx
    import torch

    from vericlue_ml.eval.onnx_networks import load_network

    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    images = synthetic_inputs(args.model, samples=args.samples, seed=args.seed)
    np.save(directory / "inputs.npy", images, allow_pickle=False)
    _torch_settings("cpu", args.threads)
    started = time.perf_counter()
    with _Memory() as memory:
        network, classifier, revisions = load_network(args.model, args.models_dir.resolve(), "cpu")
        torch.set_num_threads(args.threads)
        expected = _collect(lambda value: _torch_run(network, value, "cpu"), images)
        native = np.asarray(classifier.p_fake(images), dtype=np.float32)
        if not np.allclose(
            native, expected["probabilities"][:, ATTACK_INDICES[args.model]], atol=1e-5, rtol=1e-4
        ):
            raise ValueError("Export adapter differs from the original classifier")
        np.savez(directory / "reference.npz", **expected)
        # Avoid the fused native MHA op that has no portable ONNX representation.
        fastpath = torch.backends.mha.get_fastpath_enabled()
        try:
            torch.backends.mha.set_fastpath_enabled(False)
            with torch.inference_mode():
                program = torch.onnx.export(
                    network,
                    (torch.from_numpy(images[:1]),),
                    str(directory / "model.onnx"),
                    input_names=["images"],
                    output_names=["logits", "probabilities"],
                    opset_version=18,
                    dynamo=True,
                    external_data=True,
                    optimize=False,
                    report=True,
                    artifacts_dir=str(directory),
                )
            del program
        finally:
            torch.backends.mha.set_fastpath_enabled(fastpath)
        onnx.checker.check_model(str(directory / "model.onnx"))
    files = [directory / name for name in ("inputs.npy", "reference.npz")]
    files += sorted(directory.glob("model.onnx*"))
    metadata = {
        "format": 1,
        "model": args.model,
        "model_id": MODEL_IDS[args.model],
        "attack_index": ATTACK_INDICES[args.model],
        "dtype": "float32",
        "input_shape": list(SHAPE),
        "opset": 18,
        "samples": len(images),
        "seed": args.seed,
        "input_kind": "synthetic_rgb_patterns_not_faces",
        "source_revisions": revisions,
        "provenance": _provenance(),
        "environment": _versions(),
        "files": {p.name: sha256(p) for p in files},
        "onnx_bytes": sum(p.stat().st_size for p in files if p.name.startswith("model.onnx")),
        "export_seconds": time.perf_counter() - started,
        "memory": memory.result(),
        "status": "exported_not_yet_runtime_verified",
        "biometric_accuracy_evaluated": False,
    }
    write_json(directory / "bundle.json", metadata)
    print(json.dumps({"exported": str(directory), "model": args.model}), flush=True)


def _ort_run(directory: Path, device: str, threads: int, *, optimize: bool = True):
    import onnxruntime as ort

    provider = "CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"
    if provider not in ort.get_available_providers():
        raise ValueError("Requested execution provider is unavailable")
    if device == "cuda" and hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.graph_optimization_level = (
        ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if optimize
        else ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    )
    providers = [(provider, {"use_tf32": "0"})] if device == "cuda" else [provider]
    session = ort.InferenceSession(
        str(directory / "model.onnx"), sess_options=options, providers=providers
    )
    session.disable_fallback()
    if session.get_providers()[0] != provider:
        raise ValueError("Requested provider failed; refusing a CPU-labelled-as-GPU benchmark")

    def run(images):
        logits, probabilities = session.run(["logits", "probabilities"], {"images": images})
        return {"logits": logits, "probabilities": probabilities}

    return run, session.get_providers()


def benchmark(args) -> None:
    directory = args.bundle.resolve()
    metadata, images = _bundle(directory)
    expected = _read_outputs(directory / "reference.npz")
    cuda_reference_hash = None
    if args.device == "cuda" and args.engine == "onnx":
        expected, cuda_reference_hash = _cuda_reference(directory, metadata)
    before_gpu = _gpu_used() if args.device == "cuda" else None
    started = time.perf_counter()
    with _Memory() as memory:
        if args.engine == "torch":
            from vericlue_ml.eval.onnx_networks import load_network

            _torch_settings(args.device, args.threads)
            network, classifier, _ = load_network(
                metadata["model"], args.models_dir.resolve(), args.device
            )
            import torch

            torch.set_num_threads(args.threads)
            run = lambda value: _torch_run(network, value, args.device)  # noqa: E731
            providers = ["pytorch:" + args.device]
        else:
            run, providers = _ort_run(directory, args.device, args.threads)
        load_seconds = time.perf_counter() - started
        after_load_gpu = _gpu_used() if args.device == "cuda" else None
        actual = _collect(run, images)
        parity = compare_outputs(expected, actual, atol=args.atol, rtol=args.rtol)
        cpu_reference_parity = compare_outputs(
            _read_outputs(directory / "reference.npz"), actual, atol=args.atol, rtol=args.rtol
        )
        if args.device == "cuda" and args.engine == "torch":
            native = np.asarray(
                [classifier.p_fake(frame[None])[0] for frame in images], dtype=np.float32
            )
            scores = actual["probabilities"][:, ATTACK_INDICES[metadata["model"]]]
            parity = {
                "passed": bool(np.allclose(scores, native, atol=args.atol, rtol=args.rtol)),
                "scope": "export_adapter_vs_original_classifier_on_same_cuda_device",
                "samples": len(images),
                "max_abs_error": float(np.abs(scores - native).max()),
                "atol": args.atol,
                "rtol": args.rtol,
                "biometric_accuracy_evaluated": False,
            }
        np.savez(directory / f"{args.engine}-{args.device}-outputs.npz", **actual)
        if not parity["passed"]:
            write_json(
                directory / f"{args.engine}-{args.device}.json",
                {
                    "status": "numerical_mismatch",
                    "parity": parity,
                    "cpu_reference_parity": cpu_reference_parity,
                },
            )
            raise ValueError("Numerical equivalence check failed; benchmark not accepted")
        for index in range(args.warmup):
            run(images[index % len(images)][None])
        milliseconds = []
        for index in range(args.runs):
            begin = time.perf_counter()
            run(images[index % len(images)][None])
            milliseconds.append((time.perf_counter() - begin) * 1000)
    result = {
        "status": "ok",
        "model": metadata["model"],
        "model_id": metadata["model_id"],
        "engine": args.engine,
        "device": args.device,
        "providers": providers,
        "threads": args.threads,
        "dtype": metadata["dtype"],
        "input_shape": metadata["input_shape"],
        "input_sha256": metadata["files"]["inputs.npy"],
        "bundle_sha256": sha256(directory / "bundle.json"),
        "warmup": args.warmup,
        "latency": latency_summary(milliseconds),
        "latency_trials_ms": milliseconds,
        "load_and_integrity_seconds": load_seconds,
        "memory": memory.result(),
        "gpu_whole_device_used_mib": {
            "before": before_gpu,
            "after_load": after_load_gpu,
            "after_run": _gpu_used() if args.device == "cuda" else None,
            "scope": "snapshots_include_other_processes_not_peak_vram",
        },
        "parity": parity,
        "cpu_reference_parity": cpu_reference_parity,
        "cuda_reference_output_sha256": cuda_reference_hash,
        "output_sha256": sha256(directory / f"{args.engine}-{args.device}-outputs.npz"),
        "environment": _versions(),
        "provenance": _provenance(),
        "timing_scope": "network_only_numpy_to_device_and_back_excludes_camera_detection_alignment_io",
        "biometric_accuracy_evaluated": False,
    }
    write_json(directory / f"{args.engine}-{args.device}.json", result)
    print(
        json.dumps(
            {
                "model": metadata["model"],
                "engine": args.engine,
                "device": args.device,
                "p50_ms": result["latency"]["p50_ms"],
                "parity": True,
            }
        ),
        flush=True,
    )


def _cuda_reference(directory: Path, metadata: dict) -> tuple[dict, str]:
    """Compare conversion on the same device; preserve cross-device drift separately."""
    reference = json.loads((directory / "torch-cuda.json").read_text(encoding="utf-8"))
    output = directory / "torch-cuda-outputs.npz"
    digest = sha256(output)
    if (
        reference.get("status") != "ok"
        or reference.get("engine") != "torch"
        or reference.get("device") != "cuda"
        or reference.get("bundle_sha256") != sha256(directory / "bundle.json")
        or reference.get("input_sha256") != metadata["files"]["inputs.npy"]
        or reference.get("output_sha256") != digest
        or not reference.get("parity", {}).get("passed")
    ):
        raise ValueError("A verified matching PyTorch CUDA reference is required")
    return _read_outputs(output), digest


def summarize(args) -> None:
    directory = args.bundle.resolve()
    results = [
        json.loads((directory / f"{engine}-{args.device}.json").read_text(encoding="utf-8"))
        for engine in ("torch", "onnx")
    ]
    first, second = results
    if args.device == "cuda" and second.get("cuda_reference_output_sha256") != first.get(
        "output_sha256"
    ):
        raise ValueError("CUDA comparison uses a stale PyTorch reference")
    for field in (
        "model",
        "device",
        "dtype",
        "threads",
        "input_shape",
        "input_sha256",
        "bundle_sha256",
        "warmup",
    ):
        if first[field] != second[field]:
            raise ValueError("Benchmark settings differ")
    if (
        any(item["status"] != "ok" or not item["parity"]["passed"] for item in results)
        or first["latency"]["runs"] != second["latency"]["runs"]
    ):
        raise ValueError("Both matched benchmarks must pass")
    result = {
        "model": first["model"],
        "device": args.device,
        "results": results,
        "p50_speedup_torch_over_onnx": first["latency"]["p50_ms"] / second["latency"]["p50_ms"],
        "p95_speedup_torch_over_onnx": first["latency"]["p95_ms"] / second["latency"]["p95_ms"],
        "biometric_accuracy_evaluated": False,
        "deployment_approved": False,
        "limitations": [
            "Synthetic numerical smoke test, not APCER/BPCER/AUC.",
            "One model process at a time; excludes video decoding, face detection and preprocessing.",
            "Latency depends on current laptop load; repeated trials are not independent users.",
            "CUDA provider activation does not assert every node is assigned to GPU.",
        ],
    }
    write_json(directory / f"comparison-{args.device}.json", result)
    print(
        json.dumps(
            {
                "comparison": str(directory / f"comparison-{args.device}.json"),
                "p50_speedup": result["p50_speedup_torch_over_onnx"],
            }
        ),
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    exporter = sub.add_parser("export")
    exporter.add_argument("--model", choices=MODEL_IDS, required=True)
    exporter.add_argument(
        "--models-dir", type=Path, default=Path(os.getenv("MODELS_DIR", "models"))
    )
    exporter.add_argument("--output", type=Path, required=True)
    exporter.add_argument("--samples", type=int, default=8)
    exporter.add_argument("--seed", type=int, default=20261030)
    exporter.add_argument("--threads", type=int, default=4)
    runner = sub.add_parser("benchmark")
    runner.add_argument("--bundle", type=Path, required=True)
    runner.add_argument("--engine", choices=("torch", "onnx"), required=True)
    runner.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    runner.add_argument("--models-dir", type=Path, default=Path(os.getenv("MODELS_DIR", "models")))
    runner.add_argument("--threads", type=int, default=4)
    runner.add_argument("--warmup", type=int, default=3)
    runner.add_argument("--runs", type=int, default=20)
    runner.add_argument("--atol", type=float, default=1e-5)
    runner.add_argument("--rtol", type=float, default=1e-4)
    summary = sub.add_parser("summarize")
    summary.add_argument("--bundle", type=Path, required=True)
    summary.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args(argv)
    if hasattr(args, "threads") and not 1 <= args.threads <= 16:
        parser.error("threads must be between 1 and 16")
    if args.command == "benchmark" and (args.warmup < 1 or args.runs < 3):
        parser.error("at least one warmup and three measured runs are required")
    {"export": export, "benchmark": benchmark, "summarize": summarize}[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
