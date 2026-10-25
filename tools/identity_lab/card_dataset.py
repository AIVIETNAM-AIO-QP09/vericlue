"""Audit YOLO card annotations and prepare a detector experiment (offline)."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from PIL import Image

FIELDS = [
    "id",
    "name",
    "dob",
    "gender",
    "nationality",
    "expire_date",
    "origin_place1",
    "origin_place2",
    "current_place1",
    "current_place2",
]


def sha256(path):
    with Path(path).open("rb") as stream:
        return (
            hashlib.file_digest(stream, "sha256").hexdigest()
            if hasattr(hashlib, "file_digest")
            else hashlib.sha256(stream.read()).hexdigest()
        )


def parse_labels(text, names, width, height):
    """Validate normalized YOLO boxes; tolerate only rounding at image edges."""
    boxes = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        category = int(parts[0])
        values = list(map(float, parts[1:]))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Nonfinite coordinates")
        polygon = None
        if len(values) == 4:
            x, y, w, h = values
        elif len(values) >= 6 and len(values) % 2 == 0:
            if min(values) < 0 or max(values) > 1:
                raise ValueError("Polygon outside image")
            xs, ys = values[::2], values[1::2]
            x, y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            polygon = [[px * width, py * height] for px, py in zip(xs, ys, strict=True)]
        else:
            raise ValueError("Expected YOLO box or polygon")
        if not 0 <= category < len(names) or not all(math.isfinite(v) for v in (x, y, w, h)):
            raise ValueError("Invalid class or nonfinite coordinates")
        if (
            w <= 0
            or h <= 0
            or min(x - w / 2, y - h / 2) < -1e-6
            or max(x + w / 2, y + h / 2) > 1 + 1e-6
        ):
            raise ValueError("Box outside image or empty")
        boxes.append(
            {
                "field": names[category],
                "polygon": polygon,
                "xyxy": [
                    max(0, (x - w / 2) * width),
                    max(0, (y - h / 2) * height),
                    min(width, (x + w / 2) * width),
                    min(height, (y + h / 2) * height),
                ],
            }
        )
    return boxes


def audit(root, out):
    """Write reproducible manifests; never infer identities from filenames."""
    root, out = Path(root).resolve(), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    names = config["names"]
    if isinstance(names, dict):
        names = [names[i] for i in range(len(names))]
    rows, errors = [], []
    pixel_groups, source_groups = defaultdict(list), defaultdict(list)
    counts, sizes = Counter(), Counter()
    for split in ("train", "valid", "test"):
        images = sorted((root / split / "images").glob("*"))
        image_stems = {p.stem for p in images}
        for label in sorted((root / split / "labels").glob("*.txt")):
            if label.stem not in image_stems:
                errors.append(
                    {"file": label.relative_to(root).as_posix(), "reason": "orphan_label"}
                )
        for path in images:
            relative = path.relative_to(root).as_posix()
            label = root / split / "labels" / (path.stem + ".txt")
            try:
                with Image.open(path) as image:
                    image = image.convert("RGB")
                    width, height = image.size
                    pixel_hash = hashlib.sha256(
                        str(image.size).encode() + image.tobytes()
                    ).hexdigest()
                boxes = parse_labels(label.read_text(encoding="utf-8"), names, width, height)
            except (OSError, ValueError) as exc:
                errors.append({"file": relative, "reason": str(exc)})
                continue
            counts.update(b["field"] for b in boxes)
            sizes[f"{width}x{height}"] += 1
            row = {
                "image": relative,
                "split": split,
                "sha256": sha256(path),
                "label_sha256": sha256(label),
                "pixel_sha256": pixel_hash,
                "width": width,
                "height": height,
                "boxes": boxes,
                "cccd_candidate": any(b["field"] == "cccd" for b in boxes),
            }
            rows.append(row)
            pixel_groups[pixel_hash].append(relative)
            source_groups[path.stem.split(".rf.")[0]].append(relative)

    def cross(groups):
        return [v for v in groups.values() if len({p.split("/")[0] for p in v}) > 1]

    report = {
        "images": len(rows),
        "splits": dict(Counter(r["split"] for r in rows)),
        "cccd_candidates": dict(Counter(r["split"] for r in rows if r["cccd_candidate"])),
        "classes": names,
        "box_counts": dict(counts),
        "sizes": dict(sizes),
        "polygon_boxes": sum(b["polygon"] is not None for r in rows for b in r["boxes"]),
        "errors": errors,
        "cross_split_identical_pixels": cross(pixel_groups),
        "cross_split_source_name_candidates": cross(source_groups),
        "person_split_verified": False,
        "note": "Filename and pixel checks cannot rule out same-person leakage. CCCD class is a selection hint, not verified card type.",
    }
    (out / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Do not overwrite human-reviewed group IDs on a rerun.
    groups_path = out / "groups.csv"
    if groups_path.exists():
        with groups_path.open(encoding="utf-8-sig", newline="") as stream:
            existing = list(csv.DictReader(stream))
        known = {r["image"] for r in existing}
        with groups_path.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["image", "group_id"])
            writer.writerows(
                {"image": r["image"], "group_id": ""}
                for r in rows
                if r["cccd_candidate"] and r["image"] not in known
            )
    else:
        with groups_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["image", "group_id"])
            writer.writeheader()
            writer.writerows(
                {"image": r["image"], "group_id": ""} for r in rows if r["cccd_candidate"]
            )
    return report, rows


def grouped_split(rows, groups_path, seed=42):
    """Split supplied groups; callers must record whether they are verified."""
    with Path(groups_path).open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.DictReader(stream))
    groups = {r["image"]: r["group_id"].strip() for r in records}
    if len(groups) != len(records):
        raise ValueError("Duplicate image rows in groups.csv")
    if any(not groups.get(r["image"]) for r in rows):
        raise ValueError(
            "Fill group_id for every CCCD candidate; same person = same anonymous group_id"
        )
    duplicates = defaultdict(set)
    for row in rows:
        duplicates[row["pixel_sha256"]].add(groups[row["image"]])
    if any(len(v) > 1 for v in duplicates.values()):
        raise ValueError("Identical images assigned different identities")
    ids = sorted(
        {groups[r["image"]] for r in rows},
        key=lambda g: hashlib.sha256(f"{seed}:{g}".encode()).hexdigest(),
    )
    if len(ids) < 10:
        raise ValueError(
            "At least 10 groups required; inspect auto_group_report.json or manual groups"
        )
    n_val = max(1, round(len(ids) * 0.15))
    allocation = {
        g: ("valid" if i < n_val else "test" if i < 2 * n_val else "train")
        for i, g in enumerate(ids)
    }
    return [
        {**r, "split": allocation[groups[r["image"]]], "group_id": groups[r["image"]]} for r in rows
    ]


def export_crops(root, rows, out, limit=80):
    """Create an annotation queue, never pseudo ground truth; train images only."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "transcriptions.csv"
    if csv_path.exists():
        return csv_path
    records = []
    for row in rows:
        if row["split"] != "train" or not row["cccd_candidate"]:
            continue
        with Image.open(Path(root) / row["image"]) as image:
            image = image.convert("RGB")
            for i, box in enumerate(row["boxes"]):
                if box["field"] not in FIELDS:
                    continue
                filename = f"{row['sha256'][:20]}_{i}_{box['field']}.png"
                x1, y1, x2, y2 = box["xyxy"]
                image.crop((math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2))).save(
                    out / filename
                )
                records.append(
                    {
                        "crop": filename,
                        "image": row["image"],
                        "field": box["field"],
                        "text": "",
                        "reviewed": "false",
                    }
                )
                if len(records) >= limit:
                    break
        if len(records) >= limit:
            break
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["crop", "image", "field", "text", "reviewed"])
        writer.writeheader()
        writer.writerows(records)
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report, rows = audit(args.root, args.out)
    export_crops(args.root, rows, args.out / "recognition_queue")
    print(
        json.dumps(
            {k: v for k, v in report.items() if not k.startswith("cross_")},
            ensure_ascii=False,
            indent=2,
        )
    )
