"""Collect FACE-07 measured evidence, including rejected trials, without weights."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from vericlue_ml.eval.fp16_gend import POLICY, load_bundle, provenance, source_bundle
from vericlue_ml.eval.onnx_metrics import latency_summary, sha256, write_json


def collect(directory: Path) -> dict:
    """Validate artifact checksums and consistent engine references before aggregation."""
    metadata, _, _ = load_bundle(directory)
    engines = {}
    for engine in ["torch32", "torch16", "onnx32", "onnx16", "onnx16-noopt"]:
        path = directory / f"{engine}.json"
        if not path.exists():
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        if item["engine"] != engine.split("-")[0]:
            raise ValueError("Incorrect engine report")
        if item["status"] == "ok":
            if (
                not item["parity"]["passed"]
                or item["fp16_bundle_sha256"] != sha256(directory / "fp16-bundle.json")
                or item["input_sha256"] != metadata["source_input_sha256"]
                or item["reference_output_sha256"] != metadata["source_reference_output_sha256"]
                or item["latency"] != latency_summary(item["latency_trials_ms"])
            ):
                raise ValueError("Inconsistent benchmark evidence")
        elif item["status"] != "numerical_mismatch" or item["parity"]["passed"]:
            raise ValueError("Unknown or inconsistent failed benchmark")
        engines[engine] = item
    return {"artifact": metadata, "engines": engines}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--fp32-bundle", type=Path, required=True)
    parser.add_argument("--previous-bundle", type=Path, action="append", default=[])
    parser.add_argument("--failed-trial", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    baseline, _, _, _ = source_bundle(args.fp32_bundle)
    current = collect(args.bundle)
    if current["artifact"]["source_fp32_bundle_sha256"] != sha256(args.fp32_bundle / "bundle.json"):
        raise ValueError("Mismatched FP32 source")
    failed = [json.loads(path.read_text(encoding="utf-8")) for path in args.failed_trial]
    if any(item["status"] != "numerical_mismatch" or item["parity"]["passed"] for item in failed):
        raise ValueError("Incorrect rejected-trial record")
    try:
        gpu = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            timeout=10,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        gpu = "unavailable"
    result = {
        "policy": POLICY,
        "hardware_gpu": gpu,
        "fp32_source": baseline,
        "current": current,
        "previous": [collect(path) for path in args.previous_bundle],
        "rejected_before_export": failed,
        "provenance": provenance(),
        "biometric_accuracy_evaluated": False,
        "deployment_approved": False,
        "report_source_sha256": sha256(Path(__file__)),
    }
    write_json(args.output, result)
    for engine, item in current["engines"].items():
        print(
            engine,
            item["status"],
            item.get("latency", {}),
            item["parity"]["outputs"]["probabilities"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
