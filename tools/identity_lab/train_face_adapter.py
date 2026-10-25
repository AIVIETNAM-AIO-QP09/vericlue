"""CPU training of a regularized diagonal metric adapter on frozen AdaFace features.

This is not backbone fine-tuning. Public identities are split before training;
personal photos enter only the separate personal command after weights are frozen.
"""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from evaluate_faces import summarize
from face_matching import extract_face, pixel_hash
from identity_lab import IdentityLab, InputError, cosine, decode_image


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def split_people(rows, seed=2026):
    ids = sorted({r["identity"] for r in rows})
    if len(ids) < 10:
        raise ValueError("At least 10 source identities required even for this pilot")
    rng = np.random.default_rng(seed)
    rng.shuffle(ids)
    a, b = int(len(ids) * 0.6), int(len(ids) * 0.8)
    return {
        person: split
        for split, people in [("train", ids[:a]), ("valid", ids[a:b]), ("test", ids[b:])]
        for person in people
    }


def adapt(vector, scale):
    vector, scale = np.asarray(vector, dtype=np.float64), np.asarray(scale, dtype=np.float64)
    if (
        vector.ndim != 1
        or scale.shape != vector.shape
        or not np.isfinite(vector).all()
        or not np.isfinite(scale).all()
        or (scale <= 0).any()
    ):
        raise ValueError("Invalid adapter input")
    output = vector * scale
    norm = np.linalg.norm(output)
    if not np.isfinite(norm) or norm < 1e-12:
        raise ValueError("Invalid adapted embedding")
    return output / norm


def pair_records(rows, vectors, scale, split):
    refs = [r for r in rows if r["split"] == split and r["role"] == "reference"]
    selfs = [r for r in rows if r["split"] == split and r["role"] == "selfie"]
    transformed = {
        r["file"]: adapt(vectors[r["file"]], scale) for r in refs + selfs if r["status"] == "ok"
    }
    pairs = []
    for ref in refs:
        for selfie in selfs:
            valid = ref["status"] == selfie["status"] == "ok"
            pairs.append(
                {
                    "reference": ref["file"],
                    "selfie": selfie["file"],
                    "reference_identity": ref["identity"],
                    "selfie_identity": selfie["identity"],
                    "reference_pixel_sha256": ref["pixel_sha256"],
                    "selfie_pixel_sha256": selfie["pixel_sha256"],
                    "same_person": ref["identity"] == selfie["identity"],
                    "status": "ok" if valid else "retry",
                    "reason": None
                    if valid
                    else ";".join(
                        r.get("reason", "") for r in [ref, selfie] if r["status"] != "ok"
                    ),
                    "cosine_similarity": cosine(
                        transformed[ref["file"]], transformed[selfie["file"]]
                    )
                    if valid
                    else None,
                }
            )
    return pairs


def balanced_loss(scores, labels):
    if not labels.any() or labels.all():
        raise ValueError("Both genuine and impostor pairs required")
    return ((1 - scores[labels]) ** 2).mean() + torch.relu(scores[~labels] - 0.1).square().mean()


def prepare(root, out, context_fallback=False):
    root, out = Path(root).resolve(), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    source = json.loads((root / "manifest.json").read_text())
    rows = source["images"]
    splits = split_people(rows)
    lab = IdentityLab(face_model="adaface_ir18")
    lab._load_faces()
    from face_context import context_config, enable_context

    if context_fallback:
        enable_context(lab)
    vectors, records, seen_pixels = {}, [], {}
    for i, row in enumerate(rows):
        path = (root / row["file"]).resolve()
        if not path.is_relative_to(root) or sha(path) != row["sha256"]:
            raise ValueError("Source path/hash mismatch")
        image = decode_image(path.read_bytes())
        pixel = pixel_hash(image)
        if pixel in seen_pixels:
            raise ValueError("Duplicate decoded source image: review dataset before training")
        seen_pixels[pixel] = row["identity"]
        record = {**row, "split": splits[row["identity"]], "pixel_sha256": pixel}
        try:
            vector, evidence = extract_face(lab, image, row["role"].upper())
            vectors[row["file"]] = vector
            record.update(status="ok", evidence=evidence)
        except InputError as exc:
            record.update(status="retry", reason=str(exc))
        records.append(record)
        if (i + 1) % 10 == 0:
            print(f"Extracted {i + 1}/{len(rows)}", flush=True)
    write(
        out / "prepared.json",
        {
            "source": source["source"],
            "revision": source["revision"],
            "manifest_sha256": sha(root / "manifest.json"),
            "pipeline": context_config(lab),
            "identity_splits": splits,
            "images": records,
        },
    )
    np.savez_compressed(out / "embeddings.npz", **vectors)
    print(
        "Identity splits:",
        dict(Counter(splits.values())),
        "statuses:",
        dict(Counter(r["status"] for r in records)),
        flush=True,
    )


def train(prepared, out):
    prepared, out = Path(prepared), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    data = json.loads((prepared / "prepared.json").read_text())
    vectors = dict(np.load(prepared / "embeddings.npz", allow_pickle=False))
    rows = data["images"]
    torch.manual_seed(2026)
    torch.set_num_threads(2)
    dimension = next(iter(vectors.values())).size
    ones = np.ones(dimension)

    def tensors(split):
        pairs = [p for p in pair_records(rows, vectors, ones, split) if p["status"] == "ok"]
        left = torch.tensor(np.stack([vectors[p["reference"]] for p in pairs]), dtype=torch.float32)
        right = torch.tensor(np.stack([vectors[p["selfie"]] for p in pairs]), dtype=torch.float32)
        labels = torch.tensor([p["same_person"] for p in pairs], dtype=torch.bool)
        return left, right, labels

    training, validation = tensors("train"), tensors("valid")

    def loss(scale, batch):
        left, right, labels = batch
        left = torch.nn.functional.normalize(left * scale, dim=1)
        right = torch.nn.functional.normalize(right * scale, dim=1)
        return balanced_loss((left * right).sum(1), labels)

    logs = torch.nn.Parameter(torch.zeros(dimension))
    optimizer = torch.optim.Adam([logs], lr=0.01)
    best_loss = float(loss(torch.ones(dimension), validation))
    best, best_epoch = ones, 0
    history = [{"epoch": 0, "valid_loss": best_loss}]
    # Fixed pilot recipe: 100 epochs, 512 parameters, scale bounded to exp(+/-0.2).
    for epoch in range(1, 101):
        optimizer.zero_grad()
        objective = loss(logs.exp(), training) + 0.1 * logs.square().mean()
        objective.backward()
        optimizer.step()
        with torch.no_grad():
            logs.clamp_(-0.2, 0.2)
            valid_loss = float(loss(logs.exp(), validation))
            if valid_loss < best_loss - 1e-7:
                best_loss, best_epoch, best = valid_loss, epoch, logs.exp().numpy().copy()
        history.append(
            {"epoch": epoch, "train_loss": float(objective.detach()), "valid_loss": valid_loss}
        )
    artifact = {
        "schema": "face-diagonal-adapter/v1",
        "scale": best.tolist(),
        "pipeline": data["pipeline"],
        "selected_epoch": best_epoch,
        "train_code_sha256": sha(__file__),
        "prepared_sha256": sha(prepared / "prepared.json"),
        "embeddings_sha256": sha(prepared / "embeddings.npz"),
        "torch_version": torch.__version__,
        "identity_splits": data["identity_splits"],
        "production_ready": False,
        "recipe": {
            "seed": 2026,
            "epochs": 100,
            "lr": 0.01,
            "regularization": 0.1,
            "max_abs_log_scale": 0.2,
            "selection": "minimum validation balanced contrastive loss; epoch 0 baseline eligible",
        },
    }
    write(out / "adapter.json", artifact)
    write(out / "history.json", history)
    report = {
        "selected_epoch": best_epoch,
        "identity_counts": dict(Counter(data["identity_splits"].values())),
        "scope": "Small external-dataset pilot, identity-disjoint by source labels. Pretraining overlap and near-duplicate identities not independently verified. No population FMR claim.",
        "results": {},
    }
    for split in ["train", "valid", "test"]:
        report["results"][split] = {}
        for variant, scale in [("baseline", ones), ("adapter", best)]:
            pairs = pair_records(rows, vectors, scale, split)
            summary = summarize(pairs)
            summary["note"] = (
                "External dataset with earlier/reference and later/selfie roles; not necessarily real ID documents. Scored-only AUC; report retry coverage. Pairs share identities."
            )
            report["results"][split][variant] = summary
            write(out / f"{split}_{variant}_pairs.json", pairs)
    write(out / "report.json", report)
    print(json.dumps(report, indent=2), flush=True)


def personal(artifact_path, references, selfies, out):
    out = Path(out)
    if out.exists():
        raise ValueError("Output exists")
    artifact = json.loads(Path(artifact_path).read_text())
    lab = IdentityLab(face_model="adaface_ir18")
    lab._load_faces()
    from face_context import context_config, enable_context

    if "no_face_recovery" in artifact["pipeline"]:
        enable_context(lab)
    if context_config(lab) != artifact["pipeline"]:
        raise ValueError("Adapter pipeline mismatch")
    scale = np.array(artifact["scale"])
    cache = {}
    for role, paths in [("reference", references), ("selfie", selfies)]:
        for path in paths:
            vector, _ = extract_face(lab, decode_image(Path(path).read_bytes()), role.upper())
            cache[str(path)] = vector
    rows = []
    for ref in references:
        for selfie in selfies:
            a, b = cache[str(ref)], cache[str(selfie)]
            start = time.perf_counter()
            adapted = cosine(adapt(a, scale), adapt(b, scale))
            rows.append(
                {
                    "reference": str(ref),
                    "selfie": str(selfie),
                    "baseline": cosine(a, b),
                    "adapter": adapted,
                    "adapter_pair_math_ms": (time.perf_counter() - start) * 1000,
                }
            )
    out.parent.mkdir(parents=True, exist_ok=True)
    write(
        out,
        {
            "adapter_sha256": sha(artifact_path),
            "pairs": rows,
            "scope": "Personal score comparison after freezing weights. This command does not infer identity labels; confirm labels externally. Not an independent benchmark.",
            "inputs": [{"file": str(p), "sha256": sha(p)} for p in references + selfies],
        },
    )
    print(json.dumps(rows, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["prepare", "train"]:
        p = sub.add_parser(name)
        p.add_argument("--input", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        if name == "prepare":
            p.add_argument("--context-fallback", action="store_true")
    p = sub.add_parser("personal")
    p.add_argument("--adapter", type=Path, required=True)
    p.add_argument("--references", type=Path, nargs="+", required=True)
    p.add_argument("--selfies", type=Path, nargs="+", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.input, args.out, args.context_fallback)
    elif args.command == "train":
        train(args.input, args.out)
    else:
        personal(args.adapter, args.references, args.selfies, args.out)
