"""Launch the local lab with one fixed configuration selected by the paired comparison."""

import argparse
import json
import math
import os
from pathlib import Path


def select_config(report, auc_tolerance=0.001):
    if not math.isfinite(auc_tolerance) or not 0 <= auc_tolerance <= 1:
        raise ValueError("Invalid AUC tolerance")
    candidates = report.get("configs", {})
    if not candidates:
        raise ValueError("No comparison candidates")
    keys = list(candidates)
    for key in keys:
        item = candidates[key]
        if (
            item["total_pairs"] != candidates[keys[0]]["total_pairs"]
            or item["scored_pairs"] != candidates[keys[0]]["scored_pairs"]
            or item["pair_manifest_sha256"] != candidates[keys[0]]["pair_manifest_sha256"]
        ):
            raise ValueError("Candidates evaluated on different pairs/coverage")
        score = item.get("roc_auc_scored_pairs_only")
        if type(score) not in (int, float) or not 0 <= score <= 1:
            raise ValueError("Invalid candidate AUC")
        latency = (item.get("recognition_latency_ms") or {}).get("median")
        if type(latency) not in (int, float) or not math.isfinite(latency) or latency <= 0:
            raise ValueError("Invalid candidate latency")
    highest_auc = max(candidates[key]["roc_auc_scored_pairs_only"] for key in keys)
    eligible = [
        key
        for key in keys
        if highest_auc - candidates[key]["roc_auc_scored_pairs_only"] <= auc_tolerance
    ]
    best = min(
        eligible,
        key=lambda key: (
            candidates[key]["recognition_latency_ms"]["median"],
            -candidates[key]["roc_auc_scored_pairs_only"],
        ),
    )
    config = candidates[best]["pipeline"]
    if config["recognizer"] not in {"adaface_ir18", "arcface_r50"} or config[
        "embedding_mode"
    ] not in {"single", "flip_mean"}:
        raise ValueError("Unsupported candidate")
    return best, config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument(
        "--auc-tolerance",
        type=float,
        default=0.001,
        help="Choose fastest model within this absolute AUC gap from highest AUC; a preference, not statistical equivalence",
    )
    args = parser.parse_args()
    name, config = select_config(
        json.loads(args.comparison.read_text(encoding="utf-8")), args.auc_tolerance
    )
    os.environ["FACE_RECOGNIZER"] = config["recognizer"]
    os.environ["FACE_EMBEDDING_MODE"] = config["embedding_mode"]
    import app
    import uvicorn
    from face_matching import pipeline_config

    app.lab._load_faces()
    if pipeline_config(app.lab, config["embedding_mode"]) != config:
        raise ValueError(
            "Selected comparison uses different code/model/runtime; rerun comparison before launching this preset"
        )
    print(
        f"Selected {name}; localhost research API only, identity_verified remains false", flush=True
    )
    uvicorn.run(app.app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
