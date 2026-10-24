"""Frozen cross-age operating-point report; no threshold tuning on validation/test."""

import argparse
import json
from collections import Counter
from pathlib import Path

from calibrate_faces import ensure_disjoint, fit, metrics, validate_records
from train_face_adapter import sha, write


def age_bucket(gap):
    if gap < 3:
        raise ValueError("Protocol requires >=3-year genuine gap")
    return "3-5" if gap <= 5 else "6-10" if gap <= 10 else "11-20" if gap <= 20 else "21+"


def report(prepared, run, out):
    prepared, run, out = Path(prepared), Path(run), Path(out)
    if out.exists():
        raise ValueError("Output exists")
    data = json.loads((prepared / "prepared.json").read_text())
    artifact = json.loads((run / "adapter.json").read_text())
    if artifact["prepared_sha256"] != sha(prepared / "prepared.json") or artifact[
        "embeddings_sha256"
    ] != sha(prepared / "embeddings.npz"):
        raise ValueError("Training source differs")
    images = {r["file"]: r for r in data["images"]}
    result = {
        "adapter_sha256": sha(run / "adapter.json"),
        "selected_epoch": artifact["selected_epoch"],
        "identity_counts": dict(Counter(data["identity_splits"].values())),
        "protocol": "Threshold fit on train with zero observed impostor errors, frozen for valid/test. Earlier vs later adult faces, not ID-selfie documents.",
        "personal_images_used": False,
        "production_ready": False,
        "variants": {},
    }
    for variant in ["baseline", "adapter"]:
        train = json.loads((run / f"train_{variant}_pairs.json").read_text())
        calibration = fit(train, 0)
        ids, pixels = validate_records(train)
        record = {"calibration": calibration, "partitions": {}}
        seen_ids = set(ids)
        seen_pixels = set(pixels)
        for split in ["valid", "test"]:
            pairs = json.loads((run / f"{split}_{variant}_pairs.json").read_text())
            ensure_disjoint(
                pairs,
                {"calibration_identities": list(seen_ids), "calibration_pixels": list(seen_pixels)},
            )
            split_ids, split_pixels = validate_records(pairs)
            seen_ids.update(split_ids)
            seen_pixels.update(split_pixels)
            buckets = {}
            for pair in pairs:
                if not pair["same_person"]:
                    continue
                gap = images[pair["selfie"]]["age"] - images[pair["reference"]]["age"]
                buckets.setdefault(age_bucket(gap), []).append(pair)
            record["partitions"][split] = {
                "overall": metrics(pairs, calibration["threshold"]),
                "genuine_by_age_gap": {
                    key: metrics(rows, calibration["threshold"]) for key, rows in buckets.items()
                },
            }
        result["variants"][variant] = record
    out.parent.mkdir(parents=True, exist_ok=True)
    write(out, result)
    print(
        json.dumps(
            {k: v["partitions"]["test"]["overall"] for k, v in result["variants"].items()}, indent=2
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report(args.prepared, args.run, args.out)
