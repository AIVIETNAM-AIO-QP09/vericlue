"""Bind reviewed numerical parity evidence to the measured CPU software stack.

This verifies implementation parity only. No calibration, accuracy or decision
authorization follows from a matching report. The operator pins its SHA256.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import math
import platform
import re
from pathlib import Path

HASH = re.compile(r"^[0-9a-f]{64}$")
SOURCE_COMMIT = "52cebaf8890479d89638b0423a802af85c8cc0c6"
SCRIPT_SHA256 = "a449c9a3e523328c2a4fb671a5059937bfe52bbc512ab034d9e32fe3aaff6e32"
# Numerical paths only: adding evidence checks does not change the measured graph.
NUMERICAL_PATHS = {
    "nes2net.py": (
        "validate_samples",
        "prepare_samples",
        "map_checkpoint",
        "_load_native",
        "logits",
        "_predict",
    ),
    "_nes2net_arch.py": None,
    "antispoof.py": ("_mapped_key", "convert_state_dict"),
}


def implementation_identity(config: dict | None = None) -> dict:
    """Fingerprint graph config and numerical code, excluding evidence instrumentation."""
    import yaml

    root = Path(__file__).resolve().parent
    if config is None:
        config = yaml.safe_load((root.parents[3] / "ml/configs/nes2net.yaml").read_text("utf-8"))
    codes = {}
    for name, functions in NUMERICAL_PATHS.items():
        tree = ast.parse((root / name).read_text("utf-8"))
        # Quality/evidence instrumentation is outside the numerical calculation.
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ModuleResult"
            ):
                node.keywords = [item for item in node.keywords if item.arg != "quality"]
        if functions is not None:
            nodes = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name in functions
            ]
            # Include constants used by the numerical recipe as well as its functions.
            if name == "nes2net.py":
                nodes += [node for node in tree.body if isinstance(node, ast.Assign)]
            tree = ast.Module(body=nodes, type_ignores=[])
        codes[name] = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    return {
        "fingerprint_version": "numerical-ast-v1",
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "code_sha256": codes,
        "recipe": "first_64000_samples_repeat_if_short_no_normalization_no_trim",
    }


def validate_parity_claim(result) -> None:
    """Reject malformed or contradictory numerical-parity claims at IPC boundaries."""
    quality = result.quality
    marker = quality.get("frontend_parity_verified", False)
    digest = quality.get("parity_report_sha256")
    if (
        type(marker) is not bool
        or quality.get("calibrated", False) is not False
        or (
            marker
            and (
                result.status != "degraded"
                or not isinstance(digest, str)
                or HASH.fullmatch(digest) is None
            )
        )
        or (not marker and digest is not None)
    ):
        raise ValueError("Invalid parity claim")


def runtime_identity() -> dict:
    """Read the live numerical runtime after CPU inference settings are applied."""
    import torch

    return {
        "system": platform.system(),
        "python": platform.python_version(),
        **{k: importlib.metadata.version(k) for k in ("torch", "transformers", "numpy")},
        "cpu_threads": torch.get_num_threads(),
    }


def _comparison(value: dict) -> None:
    count = value["window_count"]
    diversity = value["diversity"]
    if (
        value["status"] != "PASS"
        or value["synthetic"] is not False
        or type(count) is not int
        or count < 32
        or type(value["independent_sample_count"]) is not int
        or value["independent_sample_count"] != count
        or diversity["all_unique"] is not True
        or any(
            type(diversity[k]) is not int or diversity[k] != count
            for k in (
                "total_records",
                "unique_window_count",
                "unique_source_count",
                "unique_audio_file_count",
                "independent_sample_count",
            )
        )
        or type(diversity["duplicate_window_count"]) is not int
        or diversity["duplicate_window_count"] != 0
        or type(diversity["duplicate_source_count"]) is not int
        or diversity["duplicate_source_count"] != 0
        or type(value["min_required_clips"]) is not int
        or value["min_required_clips"] != 32
        or type(value["sign_agreement"]) not in (float, int)
        or value["sign_agreement"] != 1.0
        or value["tolerances"]
        != {
            "max_abs_logit_diff": 1e-4,
            "max_abs_margin_diff": 1e-4,
            "sign_agreement": 1.0,
        }
        or any(type(item) not in (int, float) for item in value["tolerances"].values())
        or any(
            type(value[k]) not in (int, float)
            or not math.isfinite(value[k])
            or not 0 <= value[k] <= 1e-4
            for k in ("max_abs_logit_diff", "max_abs_margin_diff")
        )
    ):
        raise ValueError("Insufficient numerical parity evidence")


def verify_parity(
    path: Path, digest: str, checkpoint_sha256: str, runtime: dict, *, config: dict | None = None
) -> str:
    """Reject unknown runtimes, altered evidence, duplicates and failed comparisons."""
    from vericlue_ml.voice.nes2net import VERSION

    try:
        if not HASH.fullmatch(digest):
            raise ValueError("An explicit parity report SHA256 is required")
        with path.open("rb") as stream:
            raw = stream.read((1 << 20) + 1)
        if len(raw) > 1 << 20 or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Changed or oversized parity report")
        report = json.loads(raw)
        if report["model_version"] != VERSION or report["checkpoint_sha256"] != checkpoint_sha256:
            raise ValueError("Parity belongs to another model")
        if report["source_commit"] != SOURCE_COMMIT or report["script_sha256"] != SCRIPT_SHA256:
            raise ValueError("Missing parity source provenance")
        if report["implementation_binding"] != implementation_identity(config):
            raise ValueError("Unmeasured numerical implementation or graph configuration")
        if runtime["system"] == "Windows":
            measured = report["windows_runtime"]
            expected = {
                "python": measured["python"].split()[0],
                **{k: measured[k] for k in ("torch", "transformers", "numpy", "cpu_threads")},
            }
            comparison = report["windows_comparison"]
        elif runtime["system"] == "Linux":
            measured = report["wsl_converted_runtime"]
            expected = {
                k: measured[k + "_version"] for k in ("python", "torch", "transformers", "numpy")
            } | {"cpu_threads": measured["cpu_threads"]}
            comparison = report["wsl_comparison"]
        else:
            raise ValueError("Unmeasured platform")
        if expected != {k: runtime[k] for k in expected}:
            raise ValueError("Unmeasured numerical runtime")
        if type(runtime["cpu_threads"]) is not int:
            raise ValueError("Invalid runtime thread count")
        _comparison(comparison)
        count = comparison["window_count"]
        if (
            any(
                type(report[k]) is not int or report[k] != count
                for k in ("samples", "independent_pcm_windows")
            )
            or type(report["speakers"]) is not int
            or not 1 <= report["speakers"] <= count
        ):
            raise ValueError("Inconsistent sample provenance")
    except (KeyError, TypeError, OSError) as exc:
        raise ValueError("Invalid parity binding") from exc
    return digest
