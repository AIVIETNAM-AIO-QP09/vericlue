"""Recognition data and evaluation. Predictions never become ground truth automatically."""

import argparse
import hashlib
import json
import math
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from card_dataset import FIELDS, grouped_split, sha256
from PIL import Image


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def canonical(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def prepare(root, manifest, out, groups=None):
    """Crop annotated regions; preserve all source splits or use supplied groups."""
    root, out = Path(root).resolve(), Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a new output folder; reviewed labels must not be overwritten")
    rows = [
        r for r in json.loads(Path(manifest).read_text(encoding="utf-8")) if r["cccd_candidate"]
    ]
    if groups:
        rows = grouped_split(rows, groups)
    out.mkdir(parents=True, exist_ok=True)
    (out / "crops").mkdir(exist_ok=True)
    records = []
    for row in rows:
        image_path = (root / row["image"]).resolve()
        if not image_path.is_relative_to(root):
            raise ValueError("Image path outside dataset root")
        if sha256(image_path) != row["sha256"]:
            raise ValueError("Source image hash differs from audited manifest")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            if image.size != (row["width"], row["height"]):
                raise ValueError("Source size differs from annotation coordinates")
            for index, box in enumerate(row["boxes"]):
                if box["field"] not in FIELDS:
                    continue
                x1, y1, x2, y2 = box["xyxy"]
                bounds = (
                    max(0, math.floor(x1)),
                    max(0, math.floor(y1)),
                    min(image.width, math.ceil(x2)),
                    min(image.height, math.ceil(y2)),
                )
                if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                    raise ValueError("Empty annotated crop")
                uid = hashlib.sha256(
                    f"{row['image']}:{row['sha256']}:{index}".encode()
                ).hexdigest()[:24]
                crop_path = out / "crops" / (uid + ".png")
                image.crop(bounds).save(crop_path)
                records.append(
                    {
                        "uid": uid,
                        "image": row["image"],
                        "image_sha256": row["sha256"],
                        "pixel_sha256": row["pixel_sha256"],
                        "crop": "crops/" + crop_path.name,
                        "crop_sha256": sha256(crop_path),
                        "box": list(bounds),
                        "field": box["field"],
                        "split": row["split"],
                        "group_id": row.get("group_id", ""),
                        "group_source": row.get(
                            "group_source", "supplied" if groups else "unknown"
                        ),
                    }
                )
    write_json(out / "samples.json", records)
    write_json(out / "reviews.json", {})
    write_json(
        out / "dataset_info.json",
        {
            "source_root": str(root),
            "manifest_sha256": sha256(manifest),
            "samples": len(records),
            "images": len(rows),
            "fields": dict(Counter(r["field"] for r in records)),
            "splits": dict(Counter(r["split"] for r in records)),
            "person_split_verified": False,
            "note": "Annotated field crops, not detector predictions. No ground truth transcripts supplied.",
        },
    )
    return records


def predict(dataset, models, architecture="seq2seq", limit=0, split="train"):
    import torch
    from vietocr.tool.config import Cfg
    from vietocr.tool.predictor import Predictor

    dataset, models = Path(dataset), Path(models)
    torch.set_num_threads(2)
    config = Cfg.load_config_from_file(str(models / "local.yml"))
    config["device"] = "cpu"
    config["weights"] = str(models / f"vgg_{architecture}.pth")
    config["cnn"]["pretrained"] = False
    weight_hash = sha256(config["weights"])
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    reader = Predictor(config)
    output = dataset / f"predictions_{architecture}.json"
    predictions = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    if predictions and any(
        p["model_sha256"] != weight_hash or p.get("config_sha256") != config_hash
        for p in predictions.values()
    ):
        raise ValueError("Prediction cache uses another model/config; use a separate dataset copy")
    rows = json.loads((dataset / "samples.json").read_text(encoding="utf-8"))
    # Round-robin fields so bounded annotation queues are not all from one field.
    queues = defaultdict(list)
    for row in rows:
        if row["split"] == split:
            queues[row["field"]].append(row)
    ordered = []
    for i in range(max((len(q) for q in queues.values()), default=0)):
        ordered.extend(queues[field][i] for field in sorted(queues) if i < len(queues[field]))
    done = 0
    for row in ordered:
        if row["uid"] in predictions:
            continue
        path = dataset / row["crop"]
        if sha256(path) != row["crop_sha256"]:
            raise ValueError("Crop hash mismatch")
        with Image.open(path) as image:
            text, confidence = reader.predict(image.convert("RGB"), return_prob=True)
        predictions[row["uid"]] = {
            "text": str(text),
            "confidence": float(confidence),
            "model_sha256": weight_hash,
            "config_sha256": config_hash,
            "crop_sha256": row["crop_sha256"],
        }
        write_json(output, predictions)
        done += 1
        if done % 25 == 0:
            print(f"{done} new predictions; split={split}", flush=True)
        if limit and done >= limit:
            break
    print(f"Predictions saved: {output}; new={done}; ground truth unchanged", flush=True)


def evaluate_records(rows, reviews, predictions, split):
    eligible = [
        r
        for r in rows
        if r["split"] == split
        and reviews.get(r["uid"], {}).get("reviewed") is True
        and reviews[r["uid"]].get("usable") is True
    ]
    if not eligible:
        raise ValueError(
            "No human-reviewed, usable transcripts for this split; no accuracy can be computed"
        )
    stats = defaultdict(
        lambda: {"samples": 0, "exact": 0, "edits": 0, "characters": 0, "missing_predictions": 0}
    )
    for row in eligible:
        truth = canonical(reviews[row["uid"]]["text"])
        if not truth:
            raise ValueError("Empty ground truth")
        prediction = predictions.get(row["uid"])
        if prediction and prediction.get("crop_sha256") != row["crop_sha256"]:
            raise ValueError("Prediction refers to a different crop")
        text = canonical(prediction["text"]) if prediction else ""
        for key in (row["field"], "overall"):
            item = stats[key]
            item["samples"] += 1
            item["exact"] += int(text == truth)
            item["edits"] += edit_distance(truth, text)
            item["characters"] += len(truth)
            item["missing_predictions"] += int(prediction is None)
    return {
        key: {
            **value,
            "cer": value["edits"] / value["characters"],
            "exact_match": value["exact"] / value["samples"],
        }
        for key, value in stats.items()
    }


def export_reviewed(dataset, groups, out):
    """Export only reviewed transcripts, splitting reviewed groups before crops."""
    dataset, out = Path(dataset).resolve(), Path(out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a new export directory")
    rows = json.loads((dataset / "samples.json").read_text(encoding="utf-8"))
    reviews = json.loads((dataset / "reviews.json").read_text(encoding="utf-8"))
    images = {r["image"]: {"image": r["image"], "pixel_sha256": r["pixel_sha256"]} for r in rows}
    allocated = {r["image"]: r for r in grouped_split(list(images.values()), groups)}
    accepted = []
    for row in rows:
        review = reviews.get(row["uid"], {})
        if review.get("reviewed") is not True or review.get("usable") is not True:
            continue
        text = canonical(review["text"])
        if not text or any(c in review["text"] for c in "\t\r\n"):
            raise ValueError("Invalid reviewed transcript")
        accepted.append(
            {
                **row,
                "split": allocated[row["image"]]["split"],
                "group_id": allocated[row["image"]]["group_id"],
                "text": text,
            }
        )
    if {r["split"] for r in accepted} != {"train", "valid", "test"}:
        raise ValueError("Need reviewed usable transcripts in train, valid and test after grouping")
    out.mkdir(parents=True, exist_ok=True)
    (out / "crops").mkdir(exist_ok=True)
    for row in accepted:
        source = dataset / row["crop"]
        if sha256(source) != row["crop_sha256"]:
            raise ValueError("Reviewed crop changed")
        shutil.copyfile(source, out / row["crop"])
    for split in ("train", "valid", "test"):
        (out / f"{split}.txt").write_text(
            "".join(f"{r['crop']}\t{r['text']}\n" for r in accepted if r["split"] == split),
            encoding="utf-8",
        )
    write_json(out / "manifest.json", accepted)
    write_json(
        out / "provenance.json",
        {
            "samples_sha256": sha256(dataset / "samples.json"),
            "reviews_sha256": sha256(dataset / "reviews.json"),
            "groups_sha256": sha256(groups),
            "counts": dict(Counter(r["split"] for r in accepted)),
            "note": "Transcripts explicitly reviewed. Identity grouping supplied by caller; must be manually audited, not inferred as verified from nonempty IDs.",
        },
    )
    return len(accepted)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--root", required=True)
    prepare_parser.add_argument("--manifest", required=True)
    prepare_parser.add_argument("--out", required=True)
    prepare_parser.add_argument("--groups")
    predict_parser = sub.add_parser("predict")
    predict_parser.add_argument("--dataset", type=Path, required=True)
    predict_parser.add_argument("--models", required=True)
    predict_parser.add_argument(
        "--architecture", choices=["seq2seq", "transformer"], default="seq2seq"
    )
    predict_parser.add_argument("--limit", type=int, default=0)
    predict_parser.add_argument("--split", choices=["train", "valid", "test"], default="train")
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--dataset", type=Path, required=True)
    evaluate_parser.add_argument("--predictions", type=Path, required=True)
    evaluate_parser.add_argument("--split", choices=["train", "valid", "test"], default="valid")
    export_parser = sub.add_parser("export")
    export_parser.add_argument("--dataset", type=Path, required=True)
    export_parser.add_argument("--groups", type=Path, required=True)
    export_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        records = prepare(args.root, args.manifest, args.out, args.groups)
        print(f"Prepared {len(records)} crops; no ground truth generated")
    elif args.action == "predict":
        predict(args.dataset, args.models, args.architecture, args.limit, args.split)
    elif args.action == "export":
        print(f"Exported {export_reviewed(args.dataset, args.groups, args.out)} reviewed crops")
    else:
        rows = json.loads((args.dataset / "samples.json").read_text(encoding="utf-8"))
        reviews = json.loads((args.dataset / "reviews.json").read_text(encoding="utf-8"))
        predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
        metrics = evaluate_records(rows, reviews, predictions, args.split)
        result = {
            "split": args.split,
            "metrics": metrics,
            "person_split_verified": False,
            "scope": "Recognition on reviewed annotated crops only; not end-to-end OCR or a verified identity-disjoint benchmark",
            "samples_sha256": sha256(args.dataset / "samples.json"),
            "reviews_sha256": sha256(args.dataset / "reviews.json"),
            "predictions_sha256": sha256(args.predictions),
        }
        write_json(args.dataset / f"evaluation_{args.predictions.stem}_{args.split}.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
