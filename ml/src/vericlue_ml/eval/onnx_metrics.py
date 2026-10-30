"""Numerical export checks; synthetic tensors do not measure biometric accuracy."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

MODEL_IDS = {"fsvfm": "fs-vfm-vit-l-fas", "gend": "gend-clip-l14"}
ATTACK_INDICES = {"fsvfm": 0, "gend": 1}
SHAPE = (1, 3, 224, 224)


def sha256(path: Path) -> str:
    """Hash artifact bytes without loading large weights into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(root: Path, relative: str) -> Path:
    """Reject absolute paths, traversal and symlinks outside an artifact bundle."""
    path = (root / relative).resolve()
    if not relative or Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path must stay inside its bundle")
    return path


def write_json(path: Path, value: dict) -> None:
    """Atomically save finite machine-readable evidence."""
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def latency_summary(milliseconds: list[float]) -> dict:
    """Summarize measured trials, rejecting empty or invalid timings."""
    values = np.asarray(milliseconds, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Expected positive finite latency measurements")
    return {
        "runs": len(values),
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
        "mean_ms": float(values.mean()),
        "min_ms": float(values.min()),
        "max_ms": float(values.max()),
    }


def compare_outputs(reference: dict, actual: dict, *, atol: float, rtol: float) -> dict:
    """Compare logits and both class probabilities, not merely predicted labels."""
    if not all(math.isfinite(v) and v >= 0 for v in (atol, rtol)):
        raise ValueError("Invalid numerical tolerances")
    checks = {}
    for key in ("logits", "probabilities"):
        expected, observed = np.asarray(reference[key]), np.asarray(actual[key])
        if (
            expected.ndim != 2
            or expected.shape[1] != 2
            or not len(expected)
            or expected.shape != observed.shape
            or expected.dtype != np.float32
            or observed.dtype != np.float32
            or not np.isfinite(expected).all()
            or not np.isfinite(observed).all()
        ):
            raise ValueError("Expected matching finite FP32 [samples, 2] outputs")
        if key == "probabilities" and (
            (observed < 0).any()
            or (observed > 1).any()
            or not np.allclose(observed.sum(axis=1), 1, atol=1e-6, rtol=1e-6)
        ):
            raise ValueError("Invalid softmax outputs")
        delta = np.abs(observed.astype(np.float64) - expected.astype(np.float64))
        checks[key] = {
            "passed": bool(np.allclose(observed, expected, atol=atol, rtol=rtol)),
            "max_abs_error": float(delta.max()),
            "mean_abs_error": float(delta.mean()),
        }
    return {
        "passed": all(item["passed"] for item in checks.values()),
        "samples": len(reference["logits"]),
        "atol": atol,
        "rtol": rtol,
        "outputs": checks,
        "argmax_agreement": float(
            (np.argmax(reference["logits"], axis=1) == np.argmax(actual["logits"], axis=1)).mean()
        ),
        "biometric_accuracy_evaluated": False,
    }


def synthetic_inputs(model: str, *, samples: int = 8, seed: int = 20261030) -> np.ndarray:
    """Create reproducible preprocessed patterns; never read user photos or datasets."""
    if model not in MODEL_IDS or not 3 <= samples <= 64:
        raise ValueError("Expected a supported model and 3..64 samples")
    from vericlue_ml.face.fsvfm import face_tensor
    from vericlue_ml.face.gend import to_tensor

    preprocess = face_tensor if model == "fsvfm" else to_tensor
    rng = np.random.default_rng(seed)
    ramp = np.tile(np.linspace(0, 255, 224, dtype=np.uint8), (224, 1))
    patterns = [np.full((224, 224, 3), value, dtype=np.uint8) for value in (0, 127, 255)]
    patterns.append(np.stack((ramp, ramp.T, 255 - ramp), axis=-1))
    while len(patterns) < samples:
        patterns.append(rng.integers(0, 256, (224, 224, 3), dtype=np.uint8))
    return np.stack([preprocess(frame) for frame in patterns[:samples]]).astype(np.float32)
