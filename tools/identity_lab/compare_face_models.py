"""Paired exploratory model selection; shared detection/alignment, no deployed threshold."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from card_dataset import sha256
from evaluate_faces import summarize
from face_matching import align_face, face_embedding, pipeline_config, pixel_hash
from identity_lab import IdentityLab, InputError, cosine, decode_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Choose a new output directory")
    rows = json.loads((args.dataset / "pairs.json").read_text(encoding="utf-8"))
    if not rows or any(type(r.get("same_person")) is not bool for r in rows):
        raise ValueError("Manifest requires explicit boolean pair labels")
    args.out.mkdir(parents=True)
    labs = {name: IdentityLab(face_model=name) for name in ("adaface_ir18", "arcface_r50")}
    for lab in labs.values():
        lab._load_faces()
    configs = {
        f"{name}_{mode}": pipeline_config(lab, mode)
        for name, lab in labs.items()
        for mode in ("single", "flip_mean")
    }
    cache, records = {}, {key: [] for key in configs}
    timings = {name: [] for name in labs}
    started = time.perf_counter()
    for index, row in enumerate(rows):
        for role in ("reference", "selfie"):
            relative = row[role]
            if relative in cache:
                continue
            source = (args.dataset / relative).resolve()
            if not source.is_relative_to(args.dataset.resolve()):
                raise ValueError("Path escapes dataset")
            entry = {"error": None, "pixel_sha256": None, "embeddings": {}}
            cache[relative] = entry
            try:
                im = decode_image(source.read_bytes())
                entry["pixel_sha256"] = pixel_hash(im)
                aligned, _ = align_face(labs["adaface_ir18"], im, "IMAGE")
                # Alternate model order per image to reduce systematic timing bias.
                order = list(labs.items())
                if len(cache) % 2:
                    order.reverse()
                for name, lab in order:
                    tick = time.perf_counter()
                    single = face_embedding(lab._recognizer, aligned)
                    single_seconds = time.perf_counter() - tick
                    flipped = face_embedding(
                        lab._recognizer, np.ascontiguousarray(aligned[:, ::-1])
                    )
                    merged = single + flipped
                    norm = np.linalg.norm(merged)
                    if norm <= 1e-12:
                        raise RuntimeError("Degenerate flip embedding")
                    timings[name].append(
                        {
                            "single_ms": single_seconds * 1000,
                            "flip_mean_ms": (time.perf_counter() - tick) * 1000,
                        }
                    )
                    entry["embeddings"][f"{name}_single"] = single
                    entry["embeddings"][f"{name}_flip_mean"] = merged / norm
            except InputError as exc:
                entry["error"] = str(exc)
        first, second = cache[row["reference"]], cache[row["selfie"]]
        errors = [
            role + ":" + cache[row[role]]["error"]
            for role in ("reference", "selfie")
            if cache[row[role]]["error"]
        ]
        if first["pixel_sha256"] is not None and first["pixel_sha256"] == second["pixel_sha256"]:
            errors.append("E_IDENTICAL_INPUTS")
        for config in configs:
            records[config].append(
                {
                    **row,
                    "status": "retry" if errors else "ok",
                    "reason": ";".join(errors) if errors else None,
                    "reference_pixel_sha256": first["pixel_sha256"],
                    "selfie_pixel_sha256": second["pixel_sha256"],
                    "cosine_similarity": None
                    if errors
                    else cosine(first["embeddings"][config], second["embeddings"][config]),
                }
            )
        if (index + 1) % 50 == 0:
            print(
                f"{index + 1}/{len(rows)} pairs; {len(cache)} images; {time.perf_counter() - started:.1f}s",
                flush=True,
            )
    reports = {}
    for key, values in records.items():
        config = configs[key]
        mode = config["embedding_mode"]
        times = [r[mode + "_ms"] for r in timings[config["recognizer"]]]
        report = {
            **summarize(values),
            "pipeline": config,
            "recognition_latency_ms": {
                "median": float(np.median(times)),
                "p95": float(np.quantile(times, 0.95)),
            }
            if times
            else None,
            "latency_scope": "Sequential recognition on shared aligned crops; excludes detection, decode, startup; not API latency",
            "pair_manifest_sha256": sha256(args.dataset / "pairs.json"),
            "protocol": "Exploratory model selection on LFW devtest; NOT an independent final test or ID-selfie benchmark",
        }
        target = args.out / key
        target.mkdir()
        (target / "pairs.json").write_text(json.dumps(values, indent=2), encoding="utf-8")
        (target / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        reports[key] = report
    valid = [key for key in reports if reports[key]["roc_auc_scored_pairs_only"] is not None]
    ranked = sorted(valid, key=lambda key: reports[key]["roc_auc_scored_pairs_only"], reverse=True)
    result = {
        "configs": reports,
        "ranking_by_exploratory_auc": ranked,
        "provisional_candidate": ranked[0] if ranked else None,
        "selection_rule": "Highest scored-pair ROC AUC on identical pairs; no per-pair model switching; no significance claim",
        "seconds": time.perf_counter() - started,
        "unique_images": len(cache),
        "production_ready": False,
        "limitations": [
            "Dataset now used for model selection, not untouched test",
            "Pretraining identity overlap not audited",
            "No CCCD-selfie or calibrated FMR evidence",
            "Comparing these pretrained checkpoints, not proving one loss function universally superior",
        ],
    }
    (args.out / "comparison.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"ranking": ranked, "seconds": result["seconds"]}), flush=True)


if __name__ == "__main__":
    main()
