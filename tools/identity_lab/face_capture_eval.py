"""Diagnostic single/burst face matching, without thresholds or score-based frame selection."""

import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np
from evaluate_faces import summarize
from face_matching import extract_face, pipeline_config, pixel_hash
from identity_lab import IdentityLab, InputError, cosine, decode_image
from train_face_adapter import sha, write


def aggregate(vectors):
    """Equal-weight normalized mean; all supplied vectors contribute exactly once."""
    matrix = np.asarray(vectors, dtype=np.float64)
    if matrix.ndim != 2 or len(matrix) < 2 or not np.isfinite(matrix).all():
        raise ValueError("At least two finite embeddings required")
    norms = np.linalg.norm(matrix, axis=1)
    if (norms < 1e-12).any():
        raise ValueError("Zero embedding")
    matrix = matrix / norms[:, None]
    mean = matrix.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm < 1e-12:
        raise ValueError("Degenerate burst")
    similarities = [
        cosine(matrix[i], matrix[j]) for i, j in itertools.combinations(range(len(matrix)), 2)
    ]
    return mean / norm, {
        "frames": len(matrix),
        "mean_vector_norm": float(norm),
        "pairwise_cosine_min": float(min(similarities)),
        "pairwise_cosine_mean": float(np.mean(similarities)),
        "note": "Diagnostics only; no calibrated same-person or quality gate",
    }


def capture(references, selfies, out):
    if not 2 <= len(selfies) <= 10:
        raise ValueError("Provide 2–10 selfies from one intended subject/session")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    lab = IdentityLab(face_model="adaface_ir18")
    lab._load_faces()
    records, vectors, seen = [], {}, {}
    for role, paths in [("reference", references), ("selfie", selfies)]:
        for index, path in enumerate(paths):
            key = f"{role}_{index}"
            row = {"key": key, "file": str(path), "role": role, "file_sha256": sha(path)}
            start = time.perf_counter()
            try:
                image = decode_image(Path(path).read_bytes())
                row["pixel_sha256"] = pixel_hash(image)
                if row["pixel_sha256"] in seen:
                    raise InputError("E_DUPLICATE_CAPTURE_IMAGE")
                seen[row["pixel_sha256"]] = key
                embedding, evidence = extract_face(lab, image, role.upper(), out / key)
                vectors[key] = embedding
                row.update(
                    status="ok", evidence=evidence, input_size=[image.shape[1], image.shape[0]]
                )
            except InputError as exc:
                row.update(status="retry", reason=str(exc))
            row["extraction_with_debug_ms"] = (time.perf_counter() - start) * 1000
            records.append(row)
    refs = [r for r in records if r["role"] == "reference"]
    selfs = [r for r in records if r["role"] == "selfie"]
    pairs = []
    for ref, selfie in itertools.product(refs, selfs):
        ok = ref["status"] == selfie["status"] == "ok"
        pairs.append(
            {
                "reference": ref["key"],
                "selfie": selfie["key"],
                "status": "ok" if ok else "retry",
                "cosine_similarity": cosine(vectors[ref["key"]], vectors[selfie["key"]])
                if ok
                else None,
            }
        )
    burst = {"status": "retry", "reason": "E_BURST_INCOMPLETE", "scores": []}
    if all(r["status"] == "ok" for r in selfs):
        try:
            template, diagnostics = aggregate([vectors[r["key"]] for r in selfs])
            burst = {
                "status": "ok",
                "reason": None,
                "diagnostics": diagnostics,
                "scores": [
                    {
                        "reference": r["key"],
                        "cosine_similarity": cosine(vectors[r["key"]], template),
                    }
                    for r in refs
                    if r["status"] == "ok"
                ],
            }
        except ValueError:
            burst["reason"] = "E_BURST_DEGENERATE"
    report = {
        "pipeline": pipeline_config(lab),
        "images": records,
        "pairs": pairs,
        "burst": burst,
        "decision": "review",
        "identity_verified": False,
        "threshold": None,
        "policy": "Equal mean of all supplied selfies; duplicate/invalid frames block burst; no best-score selection",
        "scope": "Personal diagnostic. No ground-truth labels inferred. PAD not run; no proof these images belong to one live session.",
    }
    write(out / "report.json", report)
    print(json.dumps({"pairs": pairs, "burst": burst}, indent=2), flush=True)


def development(prepared, out):
    """Validate fixed 3-frame grouping on development identities only, not test."""
    prepared, out = Path(prepared), Path(out)
    if out.exists():
        raise ValueError("Output exists")
    data = json.loads((prepared / "prepared.json").read_text())
    vectors = dict(np.load(prepared / "embeddings.npz", allow_pickle=False))
    rows = [r for r in data["images"] if r["split"] == "valid"]
    refs = [r for r in rows if r["role"] == "reference"]
    groups = []
    for identity in sorted({r["identity"] for r in rows}):
        frames = sorted(
            [r for r in rows if r["identity"] == identity and r["role"] == "selfie"],
            key=lambda r: r["file"],
        )
        # Non-overlapping groups fixed by filename before scores, no quality selection.
        groups += [(identity, frames[i : i + 3]) for i in range(0, len(frames) - 2, 3)]
    variants = {"single_first": [], "burst_mean": []}
    for ref, (identity, frames) in itertools.product(refs, groups):
        ok = ref["status"] == "ok" and all(f["status"] == "ok" for f in frames)
        for variant in variants:
            score = None
            if ok:
                template = (
                    vectors[frames[0]["file"]]
                    if variant == "single_first"
                    else aggregate([vectors[f["file"]] for f in frames])[0]
                )
                score = cosine(vectors[ref["file"]], template)
            variants[variant].append(
                {
                    "reference": ref["file"],
                    "selfies": [f["file"] for f in frames],
                    "same_person": ref["identity"] == identity,
                    "status": "ok" if ok else "retry",
                    "reason": None if ok else "E_GROUP_INPUT",
                    "cosine_similarity": score,
                }
            )
    report = {
        "prepared_sha256": sha(prepared / "prepared.json"),
        "implementation_sha256": sha(__file__),
        "partition": "valid",
        "identity_count": len({r["identity"] for r in rows}),
        "groups": len(groups),
        "scope": "Development pilot: fixed non-overlapping 3-photo groups by filename; not live video, not independent test. Both variants use same complete groups.",
        "variants": {},
    }
    for name, pairs in variants.items():
        summary = summarize(pairs)
        summary["note"] = (
            "Scored groups only; dependent identities; no threshold selected; validation reused for development"
        )
        report["variants"][name] = {"summary": summary, "pairs": pairs}
    out.parent.mkdir(parents=True, exist_ok=True)
    write(out, report)
    print(json.dumps({k: v["summary"] for k, v in report["variants"].items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("capture")
    p.add_argument("--references", type=Path, nargs="+", required=True)
    p.add_argument("--selfies", type=Path, nargs="+", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("development")
    p.add_argument("--prepared", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "capture":
        capture(args.references, args.selfies, args.out)
    else:
        development(args.prepared, args.out)
