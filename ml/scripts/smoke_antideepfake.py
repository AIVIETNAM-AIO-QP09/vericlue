"""Four-file direction smoke, not R3 accuracy or a calibration/threshold selection run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    """Run preselected public TTS/real files and record all outcomes without reselection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--tts", type=Path, action="append", required=True)
    parser.add_argument("--real", type=Path, action="append", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if len(args.tts) != 2 or len(args.real) != 2:
        parser.error("Supply exactly two preselected TTS and two real files")
    from vericlue_ml.common.detector import DetectorInput
    from vericlue_ml.voice.antispoof import AntiDeepfakeDetector

    hardware = {}
    if args.device.startswith("cuda"):
        import torch

        hardware = {
            "gpu": torch.cuda.get_device_name(),
            "total_vram_bytes": torch.cuda.get_device_properties(0).total_memory,
            "cuda_version": torch.version.cuda,
        }
        torch.cuda.reset_peak_memory_stats()
    detector = AntiDeepfakeDetector(args.models_dir, device=args.device)
    preload_started = time.perf_counter()
    detector.preload()
    preload_seconds = time.perf_counter() - preload_started
    rows = []
    for label, paths in ((1, args.tts), (0, args.real)):
        for path in paths:
            result = detector.predict(DetectorInput(audio=path))
            row = {
                "path": str(path.resolve()),
                "sha256": digest(path),
                "label": label,
                "result": result.model_dump(mode="json"),
            }
            rows.append(row)
            print(
                json.dumps(
                    {
                        "file": path.name,
                        "label": label,
                        "status": result.status,
                        "score": result.score,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    usable = all(r["result"]["status"] == "ok" and r["result"]["score"] is not None for r in rows)
    direction = usable and min(r["result"]["score"] for r in rows if r["label"] == 1) > max(
        r["result"]["score"] for r in rows if r["label"] == 0
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        commit += "-dirty"
    if args.device.startswith("cuda"):
        hardware.update(
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),
        )
    report = {
        "date": datetime.now(UTC).isoformat(),
        "commit": commit,
        "machine": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "device": args.device,
        "hardware": hardware,
        "preload_seconds": preload_seconds,
        "versions": {
            k: importlib.metadata.version(k)
            for k in ("torch", "transformers", "torchaudio", "numpy", "safetensors")
        },
        "model_version": detector.version,
        "load_report": detector._backend.load_report,
        "n_samples": len(rows),
        "direction_ok": bool(direction),
        "criterion": "min(score TTS) > max(score real); no threshold fitting or sample reselection",
        "parity_status": "Not evaluated by smoke; run parity_antideepfake.py separately",
        "limitation": "Four-file smoke only, not R3 evaluation, not calibrated probabilities",
        "samples": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("direction_ok", direction, flush=True)
    return 0 if direction else 1


if __name__ == "__main__":
    raise SystemExit(main())
