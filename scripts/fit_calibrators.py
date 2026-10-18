"""Fit provisional calibrators using real registry detectors and calib_fit only (ROUT-01)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from vericlue_ml.common.calibration import CalibFit, CalibrationStore, fit
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module, Status
from vericlue_ml.registry import get_detector

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASETS = {
    Module.VOICE_SPOOF: ["vsasv", "vimd", "mlaad_vi"],
    Module.FACE_PAD: ["zalo2022"],
    Module.FACE_DEEPFAKE: ["wilddeepfake"],
}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


@dataclass(frozen=True)
class Sample:
    path: Path
    label: int
    group_id: str
    dataset: str


def load_samples(data_dir: Path, module: Module, datasets: list[str]) -> tuple[list[Sample], dict]:
    """Read only explicitly named calib_fit manifests; preserve connected split groups."""
    samples = []
    counts = Counter()
    seen = set()
    root = data_dir.resolve()
    for dataset in datasets:
        if Path(dataset).name != dataset or dataset in {".", ".."}:
            raise ValueError("Dataset must be a single directory name")
        manifest = root / "splits" / dataset / "calib_fit.csv"
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                label = int(row["label"])
                if label not in (0, 1):
                    raise ValueError("Binary label required")
                if row.get("split", "calib_fit") != "calib_fit":
                    raise ValueError("Only calib_fit is permitted")
                attack = row["attack_type"].strip().lower()
                if module == Module.VOICE_SPOOF and attack == "replay":
                    counts["excluded_replay"] += 1
                    continue
                if module == Module.VOICE_SPOOF and label == 1 and attack not in {"tts", "vc"}:
                    counts["excluded_other_attack"] += 1
                    continue
                if module == Module.VOICE_SPOOF and label == 0 and attack != "bonafide":
                    raise ValueError("Negative voice label must be bonafide")
                path = (root / row["path"]).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    raise ValueError(f"Missing media or path outside DATA_DIR: {path}")
                if path in seen:
                    raise ValueError(f"Duplicate media: {path}")
                seen.add(path)
                # group_id spans connected source/reference groups across datasets.
                group = row.get("group_id", "").strip()
                if not group:
                    subject = row.get("subject_id", "").strip()
                    if not subject:
                        raise ValueError("Existing group_id or subject_id required")
                    group = f"{dataset}:{subject}"
                samples.append(Sample(path, label, group, dataset))
                counts["n_pos" if label else "n_neg"] += 1
    return samples, dict(counts)


def middle_frame(video: Path, target: Path) -> None:
    """Extract the middle frame of a Zalo video to approximate the captured still."""
    import cv2

    capture = cv2.VideoCapture(str(video))
    try:
        length = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if length < 1:
            raise ValueError(f"Cannot read video frames: {video}")
        capture.set(cv2.CAP_PROP_POS_FRAMES, length // 2)
        ok, frame = capture.read()
        if not ok or not cv2.imwrite(str(target), frame):
            raise ValueError(f"Cannot extract middle frame: {video}")
    finally:
        capture.release()


def run(
    module: Module,
    data_dir: Path,
    models_dir: Path,
    output_dir: Path,
    datasets: list[str],
    device: str = "cpu",
    n_splits: int = 5,
) -> dict:
    """Stop on any unusable inference; never silently fit a selected subset."""
    module = Module(module)
    if module not in DEFAULT_DATASETS:
        raise ValueError("Unsupported calibration module")
    samples, counts = load_samples(data_dir, module, datasets)
    print(json.dumps({"module": module.value, "selected": counts}), flush=True)
    if not counts.get("n_pos") or not counts.get("n_neg"):
        raise ValueError("calib_fit must include both classes")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    )
    if dirty:
        raise ValueError("Commit implementation before fitting so provenance is reproducible")
    os.environ["DEVICE"] = device
    os.environ["MODELS_DIR"] = str(models_dir.resolve())
    detector = get_detector(module, mock=False)
    if detector.version.startswith("mock@") or Module(detector.name) != module:
        raise ValueError("Real detector required")
    detector.preload(models_dir=models_dir.resolve())
    version = detector.version
    scores = []
    with tempfile.TemporaryDirectory(prefix="vericlue-calib-") as directory:
        for index, sample in enumerate(samples):
            if module == Module.VOICE_SPOOF:
                inp = DetectorInput(audio=sample.path)
            elif module == Module.FACE_PAD and sample.path.suffix.lower() in VIDEO_SUFFIXES:
                frame = Path(directory) / "middle.png"
                middle_frame(sample.path, frame)
                inp = DetectorInput(images=[frame])
            elif sample.path.suffix.lower() in VIDEO_SUFFIXES:
                inp = DetectorInput(video=sample.path)
            else:
                inp = DetectorInput(images=[sample.path])
            result = detector.predict(inp)
            if (
                result.module != module
                or result.model_version != version
                or result.status != Status.OK
                or result.score is None
                or not math.isfinite(result.score)
            ):
                raise ValueError(
                    f"Unusable inference {index + 1}/{len(samples)}: {result.status}/{result.error_code}"
                )
            scores.append(float(result.score))
            print(f"{module.value}: {index + 1}/{len(samples)}", flush=True)
    provenance = {
        "datasets": datasets,
        "manifests": {
            dataset: hashlib.sha256(
                (data_dir / "splits" / dataset / "calib_fit.csv").read_bytes()
            ).hexdigest()
            for dataset in datasets
        },
        "input": "middle frame for PAD videos; original media otherwise",
        "selection": counts,
        "grouping": "existing connected group_id, dataset:subject_id fallback",
    }
    artifact = fit(
        CalibFit(
            scores=scores,
            labels=[s.label for s in samples],
            subject_ids=[s.group_id for s in samples],
            dataset=json.dumps(provenance, sort_keys=True),
        ),
        module=module,
        model_version=version,
        commit=commit,
        n_splits=n_splits,
    ).model_copy(update={"provisional": True})
    path = CalibrationStore(output_dir).save(artifact)
    summary = {
        "path": str(path),
        "module": module.value,
        "model_version": version,
        "method": artifact.method,
        "n_pos": artifact.n_pos,
        "n_neg": artifact.n_neg,
        "commit": commit,
        "provisional": True,
        "selection": counts,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def main() -> None:
    """CLI intentionally exposes no arbitrary manifest or split option."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, choices=[m.value for m in DEFAULT_DATASETS])
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("DATA_DIR", "data")))
    parser.add_argument("--models-dir", type=Path, default=Path(os.getenv("MODELS_DIR", "models")))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ml/configs/calibrators")
    parser.add_argument("--datasets", nargs="+")
    parser.add_argument("--device", default=os.getenv("DEVICE", "cpu"))
    parser.add_argument("--n-splits", type=int, default=5)
    args = parser.parse_args()
    module = Module(args.module)
    run(
        module,
        args.data_dir,
        args.models_dir,
        args.output_dir,
        args.datasets or DEFAULT_DATASETS[module],
        args.device,
        args.n_splits,
    )


if __name__ == "__main__":
    main()
