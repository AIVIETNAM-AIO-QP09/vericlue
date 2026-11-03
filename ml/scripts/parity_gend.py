"""FACE-02: offline CPU/FP32 parity against independently pinned upstream GenD.

Only synthetic inputs; see README-parity-gend.md. No downloads or model writes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PIN = "387a42266dd385fbe8f7626c5d3aa03eea3bfaab"
EXPECTED = {
    "detector.py": "c7cbdf2dc37ffd5612f3a6b5583027e8eaa42e5eb261eae447bf92b1919eb7b7",
    "modeling_gend.py": "4b76b83df8d0f5c59082e97ececeb67735eb79a1fa0fc09d9299710179b75ad0",
    "app_run.py": "97432055d9330f3cdc59bb97ee82579483306d84a7cc4506efdc8393db13f891",
    "LICENSE": "f478adb5d8cbcb41e0236408a98a0b44269798b026e73f2da16b9cc0e55f842a",
}


def sha(path: Path | str) -> str:
    """Hash a local file without changing it."""
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write(path: Path, obj: dict) -> None:
    """Write finite JSON evidence."""
    Path(path).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )


def offline(*a: Any, **k: Any) -> None:
    """Block network connections in numerical workers."""
    raise RuntimeError("Network prohibited in parity worker")


def verify_upstream(directory: Path) -> None:
    """Reject unreviewed reference files before any source execution."""
    for name, expected in EXPECTED.items():
        if sha(directory / name) != expected:
            raise ValueError(f"Hash mismatch: upstream/{name}")


def runtime_identity() -> dict:
    """Identify the existing interpreter and installed numerical libraries."""
    packages = {}
    for name in (
        "torch",
        "transformers",
        "safetensors",
        "numpy",
        "pillow",
        "opencv-python",
        "opencv-python-headless",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    identity = {
        "python": platform.python_version(),
        "executable": sys.executable,
        "executable_sha256": sha(sys.executable),
        "packages": packages,
    }
    identity["sha256"] = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return identity


def provenance(args: argparse.Namespace) -> dict:
    """Verify local artifacts and identify the exact wrapper/runtime under test."""
    import yaml

    from vericlue_ml.face.gend import FaceDeepfakeDetector

    verify_upstream(args.upstream_dir)
    rows = {
        e["id"]: e
        for e in yaml.safe_load((args.repo / "models/manifest.yaml").read_text(encoding="utf-8"))[
            "models"
        ]
    }
    found = []
    for model, filenames in {
        "gend-clip-l14": ["config.json", "model.safetensors"],
        "clip-vit-large-patch14": [
            "config.json",
            "preprocessor_config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.json",
            "merges.txt",
        ],
    }.items():
        for filename in filenames:
            entry = next(e for e in rows[model]["files"] if e["path"] == filename)
            actual = sha(args.models_dir / model / filename)
            if actual != entry["sha256"]:
                raise ValueError(f"Hash mismatch: {model}/{filename}")
            found.append(
                {
                    "file": f"{model}/{filename}",
                    "sha256": actual,
                    "revision": rows[model]["source"]["revision"],
                }
            )
    return {
        "models": found,
        "upstream_commit": PIN,
        "upstream_source_sha256": EXPECTED,
        "repo_commit": subprocess.check_output(
            ["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True
        ).strip(),
        "repo_dirty": bool(
            subprocess.check_output(
                ["git", "-C", str(args.repo), "status", "--porcelain"], text=True
            ).strip()
        ),
        "wrapper_sha256": sha(args.repo / "ml/src/vericlue_ml/face/gend.py"),
        "support_source_sha256": {
            name: sha(args.repo / "ml/src/vericlue_ml" / name)
            for name in ("face/pad.py", "face/frames.py", "common/device.py")
        },
        "harness_sha256": sha(__file__),
        "manifest_sha256": sha(args.repo / "models/manifest.yaml"),
        "wrapper_model_version": FaceDeepfakeDetector().version,
        "runtime_identity": runtime_identity(),
    }


def fixture() -> Any:
    """Create nine seeded synthetic normalized tensors, without external media."""
    import numpy as np

    rng = np.random.default_rng(20261103)
    pixels = rng.uniform(-2, 2, (9, 3, 224, 224)).astype(np.float32)
    pixels[0] = 0
    pixels[1] = 1
    pixels[2] = -1
    pixels[3] = np.linspace(-2, 2, 224, dtype=np.float32)[None, None, :]
    pixels[4] = ((np.indices((224, 224)).sum(axis=0) % 2) * 2 - 1).astype(np.float32)
    return pixels


def worker(args: argparse.Namespace) -> None:
    """Execute one real backend and retain all intermediate captures."""
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    socket.socket.connect = offline
    socket.create_connection = offline
    sys.path.insert(0, str(args.repo / "ml/src"))
    import numpy as np
    import PIL
    import safetensors
    import torch
    import transformers

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.manual_seed(20261103)
    torch.use_deterministic_algorithms(True)
    metadata = provenance(args)
    provenance_keys = tuple(metadata)
    metadata.update(
        report_version=1,
        runtime={
            "python": platform.python_version(),
            "executable": sys.executable,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "safetensors": safetensors.__version__,
            "numpy": np.__version__,
            "pillow": PIL.__version__,
            "device": "cpu",
            "dtype": "float32",
            "threads": torch.get_num_threads(),
            "autocast": False,
            "deterministic_algorithms": True,
        },
        backend=args.mode,
        sample_count=9,
        inference_batch_sizes=[1, 2, 9],
        class_index={"0": "real", "1": "fake"},
        label_source=f"https://github.com/yermandy/GenD/blob/{PIN}/app/run.py",
        scope="synthetic normalized tensors only; no face detection or calibration evaluation",
    )
    started = time.perf_counter()
    captured = {}

    def capture(name, value):
        captured.setdefault(name, []).append(value.detach().cpu().numpy().copy())

    if args.mode == "upstream":
        spec = importlib.util.spec_from_file_location(
            "pinned_gend", args.upstream_dir / "modeling_gend.py"
        )
        upstream = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upstream)
        config = upstream.GenDConfig.from_pretrained(
            str(args.models_dir / "gend-clip-l14"), local_files_only=True
        )
        original_backbone = config.backbone
        config.backbone = str(args.models_dir / "clip-vit-large-patch14")
        model = upstream.GenD(config)
        from safetensors.torch import load_file

        state = load_file(str(args.models_dir / "gend-clip-l14/model.safetensors"))
        if len(state) != 394:
            raise ValueError(f"Expected 394 upstream checkpoint tensors, got {len(state)}")
        loaded = model.load_state_dict(state, strict=True)
        metadata["checkpoint"] = {
            "tensor_count": len(state),
            "missing": loaded.missing_keys,
            "unexpected": loaded.unexpected_keys,
        }
        del state
        model.eval()
        model.feature_extractor.register_forward_hook(lambda m, a, o: capture("pooled", o))
        model.model.linear.register_forward_pre_hook(lambda m, a: capture("normalized", a[0]))
        model.model.linear.register_forward_hook(lambda m, a, o: capture("logits", o))
        metadata["offline_adapter"] = {
            "change": "config.backbone replaces hub ID with verified local CLIP directory",
            "original": original_backbone,
            "forward_modified": False,
        }
        metadata["attention_implementation"] = (
            model.feature_extractor.vision_model.config._attn_implementation
        )

        def infer(x):
            with torch.inference_mode():
                logits = model(torch.from_numpy(x))
                capture("probabilities", logits.softmax(dim=-1))
                return logits.softmax(dim=-1)[:, 1].cpu().numpy()
    else:
        from vericlue_ml.face.gend import _load_classifier

        model, gend_rev, clip_rev = _load_classifier(args.models_dir, "cpu")
        model._vision.register_forward_hook(lambda m, a, o: capture("pooled", o.pooler_output))
        metadata["checkpoint"] = {"gend_revision": gend_rev, "clip_revision": clip_rev}
        metadata["attention_implementation"] = model._vision.config._attn_implementation
        original_linear = torch.nn.functional.linear

        def observed_linear(inputs, weight, bias=None):
            result = original_linear(inputs, weight, bias)
            if weight is model._weight:
                capture("normalized", inputs)
                capture("logits", result)
                capture("probabilities", result.softmax(dim=-1))
            return result

        def infer(x):
            with patch("torch.nn.functional.linear", observed_linear):
                return np.asarray(model.p_fake(x), dtype=np.float32)

    metadata["load_seconds"] = time.perf_counter() - started
    inputs = fixture()
    arrays = {"input": inputs}
    for count in (1, 2, 9):
        captured.clear()
        t = time.perf_counter()
        p_fake = infer(inputs[:count])
        for key, values in captured.items():
            arrays[f"{count}_{key}"] = np.concatenate(values, axis=0)
        arrays[f"{count}_p_fake"] = p_fake
        metadata.setdefault("inference_seconds", {})[str(count)] = time.perf_counter() - t
        print(f"{args.mode}: completed {count} synthetic tensors", flush=True)
    metadata["elapsed_seconds"] = time.perf_counter() - started
    metadata["post_run_provenance_match"] = provenance(args) == {
        k: metadata[k] for k in provenance_keys
    }
    if not metadata["post_run_provenance_match"]:
        raise ValueError("Files changed during inference")
    np.savez(args.out / f"{args.mode}.npz", **arrays)
    write(args.out / f"{args.mode}.json", metadata)


def preprocessing(args: argparse.Namespace) -> int:
    """Compare resize/normalization and alignment with independent upstream code."""
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    socket.socket.connect = offline
    socket.create_connection = offline
    sys.path.insert(0, str(args.repo / "ml/src"))
    import ast

    import cv2
    import numpy as np
    from PIL import Image
    from transformers import CLIPImageProcessor

    from vericlue_ml.face.gend import align_face, to_tensor

    source = args.upstream_dir / "detector.py"
    verify_upstream(args.upstream_dir)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "align_face"
    )
    namespace = {"np": np, "cv2": cv2}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    oracle_align = namespace["align_face"]
    processor = CLIPImageProcessor.from_pretrained(
        str(args.models_dir / "clip-vit-large-patch14"), local_files_only=True
    )
    pre_provenance = provenance(args)
    import torch
    import transformers

    pre_runtime = {
        "python": platform.python_version(),
        "executable": sys.executable,
        "transformers": transformers.__version__,
        "torch": torch.__version__,
        "numpy": np.__version__,
        "opencv": cv2.__version__,
    }
    rng = np.random.default_rng(20261103)
    checks = []
    for size in (31, 224, 225, 640, 73, 112):
        bgr = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
        if size == 31:
            bgr[:] = [0, 127, 255]
        if size == 640:
            grid = np.indices((size, size)).sum(axis=0) % 2
            bgr = np.repeat((grid * 255).astype(np.uint8)[:, :, None], 3, axis=2)
        expected = processor(images=Image.fromarray(bgr[:, :, ::-1]), return_tensors="np")[
            "pixel_values"
        ][0]
        actual = to_tensor(bgr)
        passed = bool(
            np.isfinite(actual).all() and np.allclose(expected, actual, atol=1e-6, rtol=1e-6)
        )
        checks.append(
            {
                "size": size,
                "max_absolute_error": float(np.max(np.abs(expected - actual))),
                "pass": passed,
            }
        )
    alignment = []
    image = rng.integers(0, 256, size=(480, 640, 3), dtype=np.uint8)
    base = np.array([[140, 150], [230, 150], [185, 190], [155, 230], [215, 230]], dtype=np.float32)
    for angle, scale, shift in [
        (0, 1, (0, 0)),
        (17, 1, (30, 10)),
        (-23, 0.6, (-10, 40)),
        (41, 1.4, (90, -25)),
        (-8, 0.21, (-140, -140)),
        (3, 2, (300, 100)),
    ]:
        radians = np.deg2rad(angle)
        rotation = np.array(
            [[np.cos(radians), -np.sin(radians)], [np.sin(radians), np.cos(radians)]],
            dtype=np.float32,
        )
        landmarks = ((base - [185, 190]) @ rotation.T * scale + [185, 190] + shift).astype(
            np.float32
        )
        expected, _ = oracle_align(image, landmarks, target_size=None, scale=1.3)
        actual = align_face(image, landmarks, scale=1.3)
        passed = bool(np.array_equal(expected, actual))
        alignment.append(
            {
                "angle": angle,
                "landmark_scale": scale,
                "shift": shift,
                "shape": list(actual.shape),
                "pass": passed,
                "max_pixel_error": int(np.max(np.abs(expected.astype(int) - actual.astype(int))))
                if expected.shape == actual.shape
                else None,
            }
        )
    report = {
        "alignment": alignment,
        "alignment_sample_count": len(alignment),
        "alignment_source_sha256": EXPECTED["detector.py"],
        "status": "pass" if all(c["pass"] for c in checks + alignment) else "fail",
        "sample_count": len(checks),
        "atol": 1e-6,
        "rtol": 1e-6,
        "processor_class": type(processor).__name__,
        "checks": checks,
    }
    report["report_version"] = 1
    report["provenance"] = pre_provenance
    report["runtime"] = pre_runtime
    report["post_run_provenance_match"] = provenance(args) == pre_provenance
    if not report["post_run_provenance_match"]:
        raise ValueError("Files changed during preprocessing")
    write(args.out / "preprocessing.json", report)
    print(json.dumps(report))
    return 0 if report["status"] == "pass" else 1


def compare_arrays(reference: dict, candidate: dict) -> dict:
    """Validate the complete capture inventory and compare independent forwards."""
    import numpy as np

    inventory = {"input": (9, 3, 224, 224)}
    for n in (1, 2, 9):
        for key, shape in {
            "pooled": (n, 1024),
            "normalized": (n, 1024),
            "logits": (n, 2),
            "probabilities": (n, 2),
            "p_fake": (n,),
        }.items():
            inventory[f"{n}_{key}"] = shape
    report = {
        "report_version": 1,
        "sample_count": 9,
        "forward_sample_count_per_backend": 12,
        "batch_sizes": [1, 2, 9],
        "atol": 1e-5,
        "rtol": 1e-5,
        "checks": {},
        "status": "PASS",
        "errors": [],
    }
    for backend, data in (("upstream", reference), ("wrapper", candidate)):
        if set(data) != set(inventory):
            report["errors"].append(f"{backend}: missing or extra captured tensors")
            report["status"] = "UNVERIFIED"
            return report
        for name, shape in inventory.items():
            if data[name].shape != shape:
                report["errors"].append(f"{backend}: invalid shape for {name}")
                report["status"] = "UNVERIFIED"
                return report
            if not np.isfinite(data[name]).all():
                report["errors"].append(f"{backend}: nonfinite {name}")
                report["status"] = "FAIL"
                return report
    if not np.array_equal(reference["input"], candidate["input"]):
        report["status"] = "FAIL"
        report["errors"].append("Inputs differ")
    for name in inventory:
        if name == "input":
            continue
        a, b = reference[name], candidate[name]
        passed = bool(np.allclose(a, b, atol=1e-5, rtol=1e-5))
        report["checks"][name] = {
            "shape": list(a.shape),
            "finite": True,
            "max_absolute_error": float(np.max(np.abs(a - b))),
            "mean_absolute_error": float(np.mean(np.abs(a - b))),
            "pass": passed,
        }
        if not passed:
            report["status"] = "FAIL"
    for backend, data in (("upstream", reference), ("wrapper", candidate)):
        for n in (1, 2, 9):
            probabilities = data[f"{n}_probabilities"]
            logits = data[f"{n}_logits"]
            exp = np.exp(logits - logits.max(axis=1, keepdims=True))
            expected_probability = exp / exp.sum(axis=1, keepdims=True)
            invariants = {
                "fake_column_1": np.array_equal(data[f"{n}_p_fake"], probabilities[:, 1]),
                "normalized_L2": np.allclose(
                    np.linalg.norm(data[f"{n}_normalized"], axis=1), 1, atol=1e-6
                ),
                "softmax": np.allclose(probabilities, expected_probability, atol=1e-6),
            }
            for label, passed in invariants.items():
                if not passed:
                    report["status"] = "FAIL"
                    report["errors"].append(f"{backend}/{n}: {label}")
    return report


def compare(args: argparse.Namespace) -> int:
    """Validate saved numerical captures, provenance, and preprocessing evidence."""
    import numpy as np

    with (
        np.load(args.out / "upstream.npz", allow_pickle=False) as reference,
        np.load(args.out / "wrapper.npz", allow_pickle=False) as candidate,
    ):
        report = compare_arrays(dict(reference), dict(candidate))
    for backend in ("upstream", "wrapper"):
        report[backend] = json.loads((args.out / f"{backend}.json").read_text(encoding="utf-8"))
        if report[backend]["post_run_provenance_match"] is not True:
            raise ValueError(f"{backend}: post-run identity not verified")
        if report[backend]["sample_count"] != 9 or report[backend]["inference_batch_sizes"] != [
            1,
            2,
            9,
        ]:
            raise ValueError(f"{backend}: incomplete execution")
        if report[backend]["class_index"] != {"0": "real", "1": "fake"}:
            raise ValueError(f"{backend}: unverified label meaning")
    checkpoint = report["upstream"]["checkpoint"]
    if checkpoint != {"tensor_count": 394, "missing": [], "unexpected": []}:
        raise ValueError("Upstream checkpoint must load all 394 tensors strictly")
    identity_keys = (
        "models",
        "repo_commit",
        "repo_dirty",
        "wrapper_sha256",
        "support_source_sha256",
        "upstream_source_sha256",
        "runtime",
        "runtime_identity",
        "harness_sha256",
        "manifest_sha256",
        "wrapper_model_version",
        "upstream_commit",
    )
    report["cross_run_identity_match"] = all(
        report["upstream"][k] == report["wrapper"][k] for k in identity_keys
    )
    if not report["cross_run_identity_match"]:
        raise ValueError("Worker identities differ")
    current = provenance(args)
    if any(report["upstream"][k] != value for k, value in current.items()):
        raise ValueError("Current source/model/runtime identity differs from captures")
    pre = json.loads((args.out / "preprocessing.json").read_text(encoding="utf-8"))
    report["preprocessing"] = pre
    report["preprocessing_identity_match"] = pre["provenance"] == current
    if not report["preprocessing_identity_match"] or pre["post_run_provenance_match"] is not True:
        raise ValueError("Preprocessing identity not verified")
    if pre["sample_count"] != 6 or pre["alignment_sample_count"] != 6:
        raise ValueError("Incomplete preprocessing sample count")
    if len(pre["checks"]) != 6 or len(pre["alignment"]) != 6:
        raise ValueError("Missing preprocessing metrics")
    if {c["size"] for c in pre["checks"]} != {31, 224, 225, 640, 73, 112}:
        raise ValueError("Invalid preprocessing size inventory")
    for check in pre["checks"]:
        error = check["max_absolute_error"]
        if type(error) not in (float, int) or not np.isfinite(error) or error < 0:
            raise ValueError("Invalid preprocessing metric")
    alignment_inventory = {
        (0, 1, (0, 0)),
        (17, 1, (30, 10)),
        (-23, 0.6, (-10, 40)),
        (41, 1.4, (90, -25)),
        (-8, 0.21, (-140, -140)),
        (3, 2, (300, 100)),
    }
    if {
        (c["angle"], c["landmark_scale"], tuple(c["shift"])) for c in pre["alignment"]
    } != alignment_inventory:
        raise ValueError("Invalid alignment inventory")
    for check in pre["checks"] + pre["alignment"]:
        if type(check["pass"]) is not bool:
            raise ValueError("Invalid preprocessing pass flag")
    for check in pre["alignment"]:
        shape = check["shape"]
        if (
            len(shape) != 3
            or any(type(n) is not int or n <= 0 for n in shape)
            or shape[0] != shape[1]
            or shape[2] != 3
        ):
            raise ValueError("Invalid alignment shape")
        error = check["max_pixel_error"]
        if error is None and check["pass"] is False:
            report["status"] = "FAIL"  # Actual/reference shapes differed.
        elif type(error) is not int or error < 0:
            raise ValueError("Invalid alignment pixel metric")
        elif error != 0:
            report["status"] = "FAIL"
    if pre["status"] != "pass" or not all(
        c["pass"] is True for c in pre["checks"] + pre["alignment"]
    ):
        report["status"] = "FAIL"
    write(args.out / "report.json", report)
    print(json.dumps({"status": report["status"], "report": str(args.out / "report.json")}))
    return {"PASS": 0, "FAIL": 1, "UNVERIFIED": 2}[report["status"]]


def main(argv: list[str] | None = None) -> int:
    """Run isolated workers or revalidate their saved evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["upstream", "wrapper", "compare", "preprocessing", "run"], default="run"
    )
    parser.add_argument("--repo", type=Path, default=HERE.parents[1])
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--upstream-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.repo = args.repo.resolve()
    args.models_dir = args.models_dir.resolve()
    args.upstream_dir = args.upstream_dir.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(exist_ok=True, parents=True)
    if args.mode == "run" and any(args.out.iterdir()):
        print(
            json.dumps(
                {
                    "status": "UNVERIFIED",
                    "error": "Use an empty output directory; existing evidence was preserved",
                }
            ),
            file=sys.stderr,
        )
        return 2
    sys.path.insert(0, str(args.repo / "ml/src"))
    try:
        if args.mode == "run":
            for mode in ("preprocessing", "upstream", "wrapper", "compare"):
                result = subprocess.run(
                    [
                        sys.executable,
                        __file__,
                        "--mode",
                        mode,
                        "--repo",
                        str(args.repo),
                        "--models-dir",
                        str(args.models_dir),
                        "--upstream-dir",
                        str(args.upstream_dir),
                        "--out",
                        str(args.out),
                    ],
                    timeout=600,
                    check=False,
                )
                # A measured preprocessing mismatch still needs both native forwards.
                if result.returncode and not (mode == "preprocessing" and result.returncode == 1):
                    if mode == "compare" and result.returncode in (1, 2):
                        return result.returncode
                    raise RuntimeError(
                        f"{mode} worker exited {result.returncode}; see stage error JSON"
                    )
            return 0
        if args.mode == "compare":
            return compare(args)
        if args.mode == "preprocessing":
            return preprocessing(args)
        worker(args)
        return 0
    except Exception as exc:
        error = {
            "report_version": 1,
            "status": "UNVERIFIED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "mode": args.mode,
        }
        write(args.out / f"{args.mode}-error.json", error)
        write(args.out / "report.json", error)
        print(json.dumps({"status": "UNVERIFIED", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
