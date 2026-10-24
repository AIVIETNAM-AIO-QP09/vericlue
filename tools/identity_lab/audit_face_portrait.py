"""Compare fixed portrait re-localization against baseline; never select by pair score."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from face_matching import align_face, face_embedding, pipeline_config
from identity_lab import IdentityLab, InputError, cosine, decode_image


def portrait_region(image, bbox):
    """Expand an already validated single face; keep context and clip to image bounds."""
    x1, y1, x2, y2 = np.asarray(bbox, dtype=float)
    width, height = x2 - x1, y2 - y1
    if not np.isfinite([x1, y1, x2, y2]).all() or min(width, height) <= 0:
        raise ValueError("Invalid face box")
    h, w = image.shape[:2]
    box = [
        max(0, int(np.floor(x1 - width * 0.5))),
        max(0, int(np.floor(y1 - height * 0.5))),
        min(w, int(np.ceil(x2 + width * 0.5))),
        min(h, int(np.ceil(y2 + height * 0.5))),
    ]
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("Empty portrait ROI")
    return image[box[1] : box[3], box[0] : box[2]], box


def audit(lab, references, selfies, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    lab._load_faces()
    load_ms = (time.perf_counter() - started) * 1000
    vectors, records = {}, []
    for role, paths in [("reference", references), ("selfie", selfies)]:
        for index, path in enumerate(paths):
            key = f"{role}_{index}"
            image = decode_image(Path(path).read_bytes())
            record = {"key": key, "file": str(path), "role": role, "status": "ok"}
            started = time.perf_counter()
            try:
                aligned, evidence = align_face(lab, image, role.upper(), out / key / "baseline")
                detection_ms = (time.perf_counter() - started) * 1000
                started = time.perf_counter()
                vectors[key] = face_embedding(lab._recognizer, aligned)
                record.update(
                    baseline=evidence,
                    detection_alignment_debug_ms=detection_ms,
                    embedding_ms=(time.perf_counter() - started) * 1000,
                )
                if role == "reference":
                    crop, roi = portrait_region(image, evidence["bbox"])
                    started = time.perf_counter()
                    try:
                        aligned2, evidence2 = align_face(
                            lab, crop, "REFERENCE", out / key / "portrait"
                        )
                        # Keep evidence in original EXIF-corrected image coordinates.
                        evidence2["bbox"] = (np.array(evidence2["bbox"]) + roi[:2] * 2).tolist()
                        evidence2["landmarks"] = (
                            np.array(evidence2["landmarks"]) + roi[:2]
                        ).tolist()
                        vectors[key + "_portrait"] = face_embedding(lab._recognizer, aligned2)
                        record.update(
                            portrait=evidence2,
                            portrait_roi=roi,
                            portrait_embedding_agreement=cosine(
                                vectors[key], vectors[key + "_portrait"]
                            ),
                        )
                    except InputError as exc:
                        record["portrait_reason"] = str(exc)
                    record["portrait_extra_ms"] = (time.perf_counter() - started) * 1000
            except InputError as exc:
                record.update(status="retry", reason=str(exc))
            records.append(record)
            print(key, record["status"], flush=True)
    pairs = []
    for ri in range(len(references)):
        for si in range(len(selfies)):
            ref, selfie = f"reference_{ri}", f"selfie_{si}"
            row = {"reference": ref, "selfie": selfie}
            for variant, key in [("baseline", ref), ("portrait", ref + "_portrait")]:
                row[variant] = (
                    cosine(vectors[key], vectors[selfie])
                    if key in vectors and selfie in vectors
                    else None
                )
            pairs.append(row)
    result = {
        "pipeline": pipeline_config(lab),
        "model_load_ms": load_ms,
        "candidate": "single-face full image first, expand bbox by 0.5 each side, re-detect reference only",
        "scope": "Development comparison. No threshold/model selection or identity decision. Timings include debug image writes.",
        "images": records,
        "pairs": pairs,
    }
    (out / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(pairs, indent=2), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, nargs="+", required=True)
    parser.add_argument("--selfies", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    audit(IdentityLab(face_model="adaface_ir18"), args.references, args.selfies, args.out)


if __name__ == "__main__":
    main()
