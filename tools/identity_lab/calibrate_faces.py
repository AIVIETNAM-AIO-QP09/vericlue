"""Offline research threshold selection. Never enables an API identity decision."""

import argparse
import json
import math
from pathlib import Path

from card_dataset import sha256


def validate_records(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Nonempty pair list required")
    identities, pixels, pairs = set(), set(), set()
    pixel_identities = {}
    for row in rows:
        ids = [row.get(key + "_identity") for key in ("reference", "selfie")]
        hashes = [row.get(key + "_pixel_sha256") for key in ("reference", "selfie")]
        if any(not isinstance(v, str) or not v.strip() for v in ids):
            raise ValueError("Explicit reference_identity and selfie_identity required")
        if any(
            not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
            for v in hashes
        ):
            raise ValueError("Decoded image SHA-256 required for every pair")
        if type(row.get("same_person")) is not bool or row["same_person"] != (ids[0] == ids[1]):
            raise ValueError("Pair label disagrees with identity labels")
        for identity, pixel in zip(ids, hashes, strict=True):
            if pixel in pixel_identities and pixel_identities[pixel] != identity:
                raise ValueError("Same image assigned conflicting identities")
            pixel_identities[pixel] = identity
        pair = tuple(sorted(hashes))
        if pair in pairs or hashes[0] == hashes[1]:
            raise ValueError("Duplicate pair or identical input pixels")
        pairs.add(pair)
        identities.update(ids)
        pixels.update(hashes)
        score = row.get("cosine_similarity")
        if row.get("status") == "ok":
            if type(score) not in (int, float) or not math.isfinite(score) or not -1 <= score <= 1:
                raise ValueError("Invalid scored pair")
        elif row.get("status") != "retry" or score is not None or not row.get("reason"):
            raise ValueError("Retry must have a reason and no score")
    return identities, pixels


def metrics(rows, threshold):
    if not math.isfinite(threshold) or not -1 <= threshold <= math.nextafter(1.0, math.inf):
        raise ValueError("Invalid threshold")
    scored = [r for r in rows if r["status"] == "ok"]
    positive = [r for r in scored if r["same_person"]]
    negative = [r for r in scored if not r["same_person"]]
    pos_total = sum(r["same_person"] for r in rows)
    false_match = sum(r["cosine_similarity"] >= threshold for r in negative)
    false_non_match = sum(r["cosine_similarity"] < threshold for r in positive)
    return {
        "threshold": threshold,
        "comparison": "cosine >= threshold",
        "total_pairs": len(rows),
        "scored_pairs": len(scored),
        "retry_pairs": len(rows) - len(scored),
        "coverage": len(scored) / len(rows),
        "genuine_scored": len(positive),
        "impostor_scored": len(negative),
        "false_matches": false_match,
        "false_non_matches": false_non_match,
        "fmr_scored": false_match / len(negative) if negative else None,
        "fnmr_scored": false_non_match / len(positive) if positive else None,
        "genuine_not_matched_including_retry_rate": (false_non_match + pos_total - len(positive))
        / pos_total
        if pos_total
        else None,
        "note": "Empirical pair rates only. Reused identities make pairs dependent; zero observed errors does not establish a population FMR bound.",
    }


def fit(rows, target_fmr):
    validate_records(rows)
    if not 0 <= target_fmr < 1:
        raise ValueError("target_fmr must be in [0, 1)")
    negative = sorted(
        r["cosine_similarity"] for r in rows if r["status"] == "ok" and not r["same_person"]
    )
    if not negative or not any(r["status"] == "ok" and r["same_person"] for r in rows):
        raise ValueError("Calibration needs scored genuine and impostor pairs")
    # Lowest threshold satisfying the empirical impostor error budget, with ties rejected together.
    allowed = math.floor(target_fmr * len(negative))
    threshold = math.nextafter(float(negative[-allowed - 1]), math.inf)
    return metrics(rows, threshold)


def ensure_disjoint(rows, artifact):
    ids, pixels = validate_records(rows)
    if ids.intersection(artifact["calibration_identities"]):
        raise ValueError("Calibration/test identity overlap")
    if pixels.intersection(artifact["calibration_pixels"]):
        raise ValueError("Calibration/test image overlap")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fit", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument(
            "--run", type=Path, required=True, help="Directory from evaluate_faces.py"
        )
        command.add_argument("--out", type=Path, required=True)
        if name == "fit":
            command.add_argument("--target-fmr", type=float, required=True)
        else:
            command.add_argument("--calibration", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Output exists; choose a new path")
    rows = json.loads((args.run / "pairs.json").read_text(encoding="utf-8"))
    summary = json.loads((args.run / "summary.json").read_text(encoding="utf-8"))
    config = summary.get("pipeline")
    if not config:
        raise ValueError("Missing pipeline provenance; rerun evaluation with current tool")
    identities, pixels = validate_records(rows)
    if args.command == "fit":
        result = {
            "schema_version": "face-calibration-lab/v1",
            "pipeline": config,
            "target_empirical_fmr": args.target_fmr,
            "calibration_metrics": fit(rows, args.target_fmr),
            "calibration_identities": sorted(identities),
            "calibration_pixels": sorted(pixels),
            "calibration_pairs_sha256": sha256(args.run / "pairs.json"),
            "production_ready": False,
        }
    else:
        artifact = json.loads(args.calibration.read_text(encoding="utf-8"))
        if (
            artifact.get("schema_version") != "face-calibration-lab/v1"
            or artifact.get("pipeline") != config
        ):
            raise ValueError("Calibration schema/model/pipeline/runtime mismatch")
        ensure_disjoint(rows, artifact)
        result = {
            "schema_version": "face-threshold-test-lab/v1",
            "pipeline": config,
            "calibration_sha256": sha256(args.calibration),
            "test_pairs_sha256": sha256(args.run / "pairs.json"),
            "metrics": metrics(rows, artifact["calibration_metrics"]["threshold"]),
            "identity_and_pixel_disjoint": True,
            "production_ready": False,
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(f"Saved {args.out}; research only, not an identity approval threshold")


if __name__ == "__main__":
    main()
