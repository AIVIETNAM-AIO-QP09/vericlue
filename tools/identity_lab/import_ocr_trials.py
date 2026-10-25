"""Import detector trial crops into human review without inventing ground truth."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from card_dataset import sha256
from PIL import Image, ImageOps
from recognition_data import write_json


def import_trials(results, source_root, out):
    source_root, out = Path(source_root).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError("Choose a new dataset folder; never overwrite reviews")
    samples, primary, secondary, audit = [], {}, {}, []
    prepared = []
    seen = set()
    # Validate everything before creating output.
    for result_path in map(Path, results):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        source = (source_root / result["image"]).resolve()
        if not source.is_relative_to(source_root) or not source.is_file():
            raise ValueError("Invalid source image")
        image_hash = sha256(source)
        with Image.open(source) as image:
            rgb = ImageOps.exif_transpose(image).convert("RGB")
            pixel_hash = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        for detection in result["detections"]:
            crop = (result_path.parent / detection["crop"]).resolve()
            if not crop.is_relative_to(result_path.parent.resolve()) or not crop.is_file():
                raise ValueError("Invalid crop path")
            crop_hash = sha256(crop)
            uid = hashlib.sha256(
                f"{image_hash}:{detection['field']}:{detection['box']}:{crop_hash}".encode()
            ).hexdigest()[:24]
            if uid in seen:
                raise ValueError("Duplicate trial crop")
            seen.add(uid)
            samples.append(
                {
                    "uid": uid,
                    "image": source.relative_to(source_root).as_posix(),
                    "image_sha256": image_hash,
                    "pixel_sha256": pixel_hash,
                    "crop": f"crops/{uid}.png",
                    "crop_sha256": crop_hash,
                    "box": detection["box"],
                    "field": detection["field"],
                    "split": "train",
                    "group_id": "",
                    "group_source": "unknown",
                    "annotation_source": "model_predicted_box_not_ground_truth",
                }
            )
            primary[uid] = {
                "text": detection.get("text", ""),
                "confidence": detection.get("recognition_score"),
            }
            comparison = detection.get("comparison", {})
            if "comparison_text" in comparison:
                secondary[uid] = {
                    "text": comparison["comparison_text"],
                    "confidence": comparison.get("comparison_confidence"),
                }
            prepared.append((crop, uid))
        audit.append(
            {
                "image": result["image"],
                "result_sha256": sha256(result_path),
                "detected_regions": len(result["detections"]),
                "missing_field_labels": result.get("missing_fields", []),
                "note": "Missing labels are not proof of absent text. Review full source for missed lines and wrong field assignment.",
            }
        )
    (out / "crops").mkdir(parents=True)
    for crop, uid in prepared:
        shutil.copyfile(crop, out / "crops" / f"{uid}.png")
    for filename, value in {
        "samples.json": samples,
        "reviews.json": {},
        "predictions_seq2seq.json": primary,
        "predictions_transformer.json": secondary,
        "dataset_info.json": {
            "source_root": str(source_root),
            "scope": "Development diagnostics only; train label is UI partition, not an approved training split. Human crop review required. No identity grouping or ground truth inferred.",
        },
        "detection_audit.json": audit,
    }.items():
        write_json(out / filename, value)
    return len(samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(
        f"Imported {import_trials(args.results, args.source_root, args.out)} crops; zero reviewed labels"
    )


if __name__ == "__main__":
    main()
