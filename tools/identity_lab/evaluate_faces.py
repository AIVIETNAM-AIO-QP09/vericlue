"""Score official LFW development-test pairs without fitting a test threshold."""

import argparse
import json
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import numpy as np
from card_dataset import sha256
from face_matching import EMBEDDING_MODES, extract_face, pipeline_config, pixel_hash
from identity_lab import IdentityLab, InputError, cosine, decode_image


def summarize(records):
    valid = [r for r in records if r["status"] == "ok"]
    positive = np.array([r["cosine_similarity"] for r in valid if r["same_person"]])
    negative = np.array([r["cosine_similarity"] for r in valid if not r["same_person"]])
    auc = (
        float(
            ((positive[:, None] > negative).sum() + 0.5 * (positive[:, None] == negative).sum())
            / (len(positive) * len(negative))
        )
        if len(positive) and len(negative)
        else None
    )

    def distribution(values):
        return (
            dict(
                zip(
                    ["min", "p05", "median", "p95", "max"],
                    map(float, np.quantile(values, [0, 0.05, 0.5, 0.95, 1])),
                    strict=True,
                )
            )
            if len(values)
            else None
        )

    return {
        "total_pairs": len(records),
        "scored_pairs": len(valid),
        "unscored_pairs": len(records) - len(valid),
        "same_person_total": sum(r["same_person"] for r in records),
        "different_person_total": sum(not r["same_person"] for r in records),
        "same_person_scored": len(positive),
        "different_person_scored": len(negative),
        "roc_auc_scored_pairs_only": auc,
        "same_person_similarity": distribution(positive),
        "different_person_similarity": distribution(negative),
        "unscored_reasons": dict(Counter(r.get("reason") for r in records if r["status"] != "ok")),
        "threshold": None,
        "accuracy_at_threshold": None,
        "note": "ROC AUC excludes unscored pairs; coverage is reported separately. Not ID/selfie accuracy. No threshold selected from test.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--embedding-mode", choices=EMBEDDING_MODES, default="single")
    parser.add_argument("--recognizer", choices=("adaface_ir18", "arcface_r50"))
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Choose new output directory")
    args.out.mkdir(parents=True, exist_ok=True)
    rows = json.loads((args.dataset / "pairs.json").read_text())
    if not rows or any(type(r.get("same_person")) is not bool for r in rows):
        raise ValueError("Manifest requires explicit boolean pair labels")
    manifest_hash = sha256(args.dataset / "pairs.json")
    lab = IdentityLab(face_model=args.recognizer)
    lab._load_faces()
    config = pipeline_config(lab, args.embedding_mode)
    cache = {}
    hashes = {}
    records = []
    started = time.perf_counter()
    for row in rows:
        errors = []
        embeddings = []
        for key in ("reference", "selfie"):
            relative = row[key]
            source = (args.dataset / relative).resolve()
            if not source.is_relative_to(args.dataset.resolve()):
                raise ValueError("Image path escapes dataset")
            if relative not in cache:
                try:
                    image = decode_image(source.read_bytes())
                    hashes[relative] = pixel_hash(image)
                    embedding, evidence = extract_face(
                        lab, image, "IMAGE", embedding_mode=args.embedding_mode
                    )
                    cache[relative] = (embedding, None)
                except InputError as exc:
                    cache[relative] = (None, str(exc))
            embedding, error = cache[relative]
            embeddings.append(embedding)
            if error:
                errors.append(key + ":" + error)
        if hashes.get(row["reference"]) is not None and hashes.get(row["reference"]) == hashes.get(
            row["selfie"]
        ):
            errors.append("E_IDENTICAL_INPUTS")
        result = {
            **row,
            "status": "retry" if errors else "ok",
            "reason": ";".join(errors) if errors else None,
            "cosine_similarity": None if errors else cosine(*embeddings),
            "reference_pixel_sha256": hashes.get(row["reference"]),
            "selfie_pixel_sha256": hashes.get(row["selfie"]),
        }
        records.append(result)
        if len(records) % 50 == 0:
            print(
                f"{len(records)}/{len(rows)} pairs; {len(cache)} unique images; {time.perf_counter() - started:.1f}s",
                flush=True,
            )
            (args.out / "pairs.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    report = {
        **summarize(records),
        "seconds": round(time.perf_counter() - started, 2),
        "unique_images": len(cache),
        "pair_manifest_sha256": manifest_hash,
        "detector_sha256": sha256(lab._detector._model_path),
        "recognizer_sha256": sha256(lab._recognizer.model_path),
        "versions": {name: version(name) for name in ["uniface", "onnxruntime", "numpy"]},
        "pipeline": config,
        "protocol": "User pair manifest; see dataset provenance. Pretrained identity overlap not audited. No threshold fitted.",
    }
    (args.out / "pairs.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
