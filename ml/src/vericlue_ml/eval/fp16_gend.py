"""FACE-07: export and benchmark GenD mixed FP16 against verified same-GPU FP32.

No server integration, new decision threshold, dataset access or network download.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from vericlue_ml.eval.onnx_export import (
    _bundle,
    _collect,
    _cuda_reference,
    _gpu_used,
    _Memory,
    _ort_run,
    _provenance,
    _torch_run,
    _torch_settings,
    _versions,
)
from vericlue_ml.eval.onnx_metrics import (
    compare_outputs,
    inside,
    latency_summary,
    sha256,
    write_json,
)

POLICY = {
    "probability_atol": 0.001,
    "logits_atol": 0.01,
    "logits_rtol": 0.001,
    "argmax_agreement": 1.0,
}
PRECISION = "fp16_vision_fp32_layernorm_head_io"


def provenance() -> dict:
    result = _provenance()
    result["fp16_source_sha256"] = {
        name: sha256(Path(__file__).with_name(name))
        for name in ("fp16_gend.py", "fp16_networks.py")
    }
    return result


def parity(reference: dict, actual: dict) -> dict:
    """Predeclared numerical budget, not a biometric acceptance threshold."""
    report = compare_outputs(
        reference, actual, atol=POLICY["logits_atol"], rtol=POLICY["logits_rtol"]
    )
    if len(reference["logits"]) != len(reference["probabilities"]):
        raise ValueError("Mismatched reference sample counts")
    probability_ok = bool(
        np.allclose(
            actual["probabilities"],
            reference["probabilities"],
            atol=POLICY["probability_atol"],
            rtol=0,
        )
    )
    report["outputs"]["probabilities"]["passed"] = probability_ok
    report["passed"] = bool(
        report["outputs"]["logits"]["passed"] and probability_ok and report["argmax_agreement"] == 1
    )
    report["policy"] = POLICY.copy()
    report["reference"] = "verified_same_device_pytorch_fp32"
    return report


def source_bundle(path: Path) -> tuple[dict, np.ndarray, dict, str]:
    metadata, images = _bundle(path)
    if metadata["model"] != "gend":
        raise ValueError("FACE-07 only accepts the verified GenD FP32 bundle")
    reference, digest = _cuda_reference(path, metadata)
    return metadata, images, reference, digest


def export(args) -> None:
    import onnx
    import torch

    from vericlue_ml.eval.fp16_networks import GendMixedHalf
    from vericlue_ml.face.gend import _load_classifier

    metadata, images, reference, digest = source_bundle(args.fp32_bundle.resolve())
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    _torch_settings("cuda", args.threads)
    started = time.perf_counter()
    with _Memory() as memory:
        classifier, revision, clip_revision = _load_classifier(args.models_dir.resolve(), "cuda")
        network = GendMixedHalf(classifier).eval()
        actual = _collect(lambda value: _torch_run(network, value, "cuda"), images)
        check = parity(reference, actual)
        np.save(destination / "inputs.npy", images, allow_pickle=False)
        np.savez(destination / "fp32-reference.npz", **reference)
        np.savez(destination / "torch-fp16-export-outputs.npz", **actual)
        if not check["passed"]:
            write_json(
                destination / "export-failure.json",
                {"status": "numerical_mismatch", "parity": check, "provenance": provenance()},
            )
            raise ValueError("FP16 candidate exceeds the predeclared numerical budget")
        previous = torch.backends.mha.get_fastpath_enabled()
        try:
            torch.backends.mha.set_fastpath_enabled(False)
            with torch.inference_mode():
                program = torch.onnx.export(
                    network,
                    (torch.from_numpy(images[:1]).cuda(),),
                    str(destination / "model.onnx"),
                    input_names=["images"],
                    output_names=["logits", "probabilities"],
                    opset_version=18,
                    dynamo=True,
                    external_data=True,
                    optimize=False,
                    report=True,
                    artifacts_dir=str(destination),
                )
            del program
        finally:
            torch.backends.mha.set_fastpath_enabled(previous)
        onnx.checker.check_model(str(destination / "model.onnx"))
    graph = onnx.load(str(destination / "model.onnx"), load_external_data=False)
    counts = {}
    for tensor in graph.graph.initializer:
        dtype = onnx.TensorProto.DataType.Name(tensor.data_type)
        counts[dtype] = counts.get(dtype, 0) + int(np.prod(tensor.dims))
    if not counts.get("FLOAT16") or counts.get("FLOAT", 0) > counts["FLOAT16"]:
        raise ValueError("Export did not reduce the backbone weights to FP16")
    files = [destination / name for name in ["inputs.npy", "fp32-reference.npz"]] + sorted(
        destination.glob("model.onnx*")
    )
    result = {
        "format": 1,
        "model": "gend",
        "precision": PRECISION,
        "input_dtype": "float32",
        "output_dtype": "float32",
        "input_shape": metadata["input_shape"],
        "samples": len(images),
        "policy": POLICY.copy(),
        "source_fp32_bundle_sha256": sha256(args.fp32_bundle / "bundle.json"),
        "source_input_sha256": metadata["files"]["inputs.npy"],
        "source_reference_output_sha256": digest,
        "source_revisions": {"gend": revision, "clip": clip_revision},
        "files": {path.name: sha256(path) for path in files},
        "initializer_elements_by_dtype": counts,
        "onnx_bytes": sum(
            path.stat().st_size for path in files if path.name.startswith("model.onnx")
        ),
        "export_seconds": time.perf_counter() - started,
        "torch_fp16_parity": check,
        "memory": memory.result(),
        "environment": _versions(),
        "provenance": provenance(),
        "biometric_accuracy_evaluated": False,
        "deployment_approved": False,
    }
    write_json(destination / "fp16-bundle.json", result)
    print(
        json.dumps({"exported": str(destination), "bytes": result["onnx_bytes"], "parity": check}),
        flush=True,
    )


def load_bundle(path: Path) -> tuple[dict, np.ndarray, dict]:
    result = json.loads((path / "fp16-bundle.json").read_text(encoding="utf-8"))
    if (
        result["format"] != 1
        or result["model"] != "gend"
        or result["precision"] != PRECISION
        or result["policy"] != POLICY
    ):
        raise ValueError("Unsupported FP16 bundle or changed numerical budget")
    required = {"inputs.npy", "fp32-reference.npz", "model.onnx"}
    if not required.issubset(result["files"]):
        raise ValueError("Missing mandatory FP16 artifact checksums")
    if result["files"]["inputs.npy"] != result["source_input_sha256"]:
        raise ValueError("FP16 inputs differ from the verified FP32 inputs")
    for relative, expected in result["files"].items():
        if sha256(inside(path, relative)) != expected:
            raise ValueError("FP16 artifact integrity mismatch")
    images = np.load(path / "inputs.npy", allow_pickle=False)
    if (
        images.dtype != np.float32
        or result["samples"] < 1
        or images.shape != (result["samples"], 3, 224, 224)
        or not np.isfinite(images).all()
    ):
        raise ValueError("Invalid FP16 bundle inputs")
    with np.load(path / "fp32-reference.npz", allow_pickle=False) as values:
        reference = {key: values[key] for key in ["logits", "probabilities"]}
    return result, images, reference


def benchmark(args) -> None:
    metadata, images, reference = load_bundle(args.bundle.resolve())
    fp32_meta, _, source_reference, digest = source_bundle(args.fp32_bundle.resolve())
    if (
        metadata["source_fp32_bundle_sha256"] != sha256(args.fp32_bundle / "bundle.json")
        or metadata["source_reference_output_sha256"] != digest
        or metadata["source_input_sha256"] != fp32_meta["files"]["inputs.npy"]
    ):
        raise ValueError("FP32 source/reference has changed")
    if any(not np.array_equal(reference[key], source_reference[key]) for key in source_reference):
        raise ValueError("Copied reference differs from the verified FP32 outputs")
    gpu_before = _gpu_used()
    started = time.perf_counter()
    with _Memory() as memory:
        if args.engine.startswith("torch"):
            from vericlue_ml.eval.onnx_networks import load_network

            _torch_settings("cuda", args.threads)
            network, classifier, _ = load_network("gend", args.models_dir.resolve(), "cuda")
            if args.engine == "torch16":
                from vericlue_ml.eval.fp16_networks import GendMixedHalf

                network = GendMixedHalf(classifier).eval()
            run = lambda value: _torch_run(network, value, "cuda")  # noqa: E731
            providers = ["pytorch:cuda"]
        else:
            directory = args.bundle if args.engine == "onnx16" else args.fp32_bundle
            run, providers = _ort_run(directory.resolve(), "cuda", args.threads)
        load_seconds = time.perf_counter() - started
        gpu_after_load = _gpu_used()
        actual = _collect(run, images)
        check = (
            parity(reference, actual)
            if args.engine.endswith("16")
            else compare_outputs(reference, actual, atol=1e-5, rtol=1e-4)
        )
        np.savez(args.bundle / (args.engine + "-outputs.npz"), **actual)
        if not check["passed"]:
            write_json(
                args.bundle / (args.engine + ".json"),
                {
                    "status": "numerical_mismatch",
                    "engine": args.engine,
                    "parity": check,
                    "provenance": provenance(),
                },
            )
            raise ValueError("Candidate fails numerical budget; no accepted timing")
        for index in range(args.warmup):
            run(images[index % len(images)][None])
        measurements = []
        for index in range(args.runs):
            begin = time.perf_counter()
            run(images[index % len(images)][None])
            measurements.append((time.perf_counter() - begin) * 1000)
    result = {
        "status": "ok",
        "engine": args.engine,
        "model": "gend",
        "precision": PRECISION if args.engine.endswith("16") else "float32",
        "device": "cuda",
        "providers": providers,
        "input_sha256": metadata["source_input_sha256"],
        "reference_output_sha256": digest,
        "fp16_bundle_sha256": sha256(args.bundle / "fp16-bundle.json"),
        "threads": args.threads,
        "warmup": args.warmup,
        "latency": latency_summary(measurements),
        "latency_trials_ms": measurements,
        "load_seconds_excluding_bundle_validation": load_seconds,
        "memory": memory.result(),
        "gpu_whole_device_used_mib": {
            "before": gpu_before,
            "after_load": gpu_after_load,
            "after_run": _gpu_used(),
            "scope": "snapshots_include_other_processes_not_peak_vram",
        },
        "parity": check,
        "environment": _versions(),
        "provenance": provenance(),
        "timing_scope": "network_only_numpy_to_gpu_and_back_excludes_capture_detection_alignment",
        "biometric_accuracy_evaluated": False,
        "deployment_approved": False,
    }
    write_json(args.bundle / (args.engine + ".json"), result)
    print(
        json.dumps({"engine": args.engine, "p50_ms": result["latency"]["p50_ms"], "parity": True}),
        flush=True,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    exporter = commands.add_parser("export")
    exporter.add_argument("--output", type=Path, required=True)
    runner = commands.add_parser("benchmark")
    runner.add_argument("--bundle", type=Path, required=True)
    runner.add_argument(
        "--engine", choices=["torch32", "torch16", "onnx32", "onnx16"], required=True
    )
    runner.add_argument("--warmup", type=int, default=3)
    runner.add_argument("--runs", type=int, default=30)
    for command in [exporter, runner]:
        command.add_argument("--fp32-bundle", type=Path, required=True)
        command.add_argument("--models-dir", type=Path, required=True)
        command.add_argument("--threads", type=int, default=4)
    args = parser.parse_args(argv)
    if not 1 <= args.threads <= 16:
        parser.error("threads must be 1..16")
    if args.command == "benchmark" and (args.warmup < 1 or args.runs < 3):
        parser.error("warmup >=1 and runs >=3 required")
    {"export": export, "benchmark": benchmark}[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
