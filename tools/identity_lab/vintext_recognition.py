"""Prepare original VinText quadrilateral TXT annotations for recognition only."""

import hashlib
import io
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def annotation(line):
    parts = line.strip("\ufeff\r\n").split(",", 8)
    if len(parts) != 9:
        raise ValueError("Expected x1,y1,x2,y2,x3,y3,x4,y4,transcript")
    points = np.asarray([float(v) for v in parts[:8]], dtype=np.float32).reshape(4, 2)
    if not np.isfinite(points).all():
        raise ValueError("Nonfinite polygon")
    text = unicodedata.normalize("NFC", parts[8].strip())
    return points, text


def rectify(image, points):
    # Original annotation order is TL, TR, BR, BL; preserve reading direction.
    h, w = image.shape[:2]
    if (points < 0).any() or (points[:, 0] > w - 1).any() or (points[:, 1] > h - 1).any():
        raise ValueError("Polygon outside image")
    if not cv2.isContourConvex(points) or abs(cv2.contourArea(points)) < 4:
        raise ValueError("Degenerate/nonconvex polygon")
    width = round(max(np.linalg.norm(points[1] - points[0]), np.linalg.norm(points[2] - points[3])))
    height = round(
        max(np.linalg.norm(points[3] - points[0]), np.linalg.norm(points[2] - points[1]))
    )
    if min(width, height) < 2 or max(width, height) > 8192:
        raise ValueError("Invalid crop size")
    target = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    return cv2.warpPerspective(image, cv2.getPerspectiveTransform(points, target), (width, height))


def discover(root):
    """Match original VinText im0001.jpg to gt_1.txt, without guessing splits."""
    root = Path(root)
    aliases = {
        "train_images": "train",
        "training": "train",
        "test_image": "test",
        "test_images": "test",
        "test": "test",
        "unseen_test_images": "unseen_test",
        "unseen_test": "unseen_test",
        # Kaggle names this partition val_image; do not claim it is original unseen_test.
        "val_image": "dataset_val",
    }
    images, ignored_crops, other_image_dirs = {}, 0, Counter()
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        # Kaggle bundles recognition crops beside the original scene images.
        # A crop im0001_1 is not a scene im0001 and has no independent polygon TXT.
        if re.fullmatch(r"im[0-9]+_[0-9]+", p.stem):
            ignored_crops += 1
            continue
        splits = {aliases[x] for x in p.relative_to(root).parts[:-1] if x in aliases}
        if len(splits) != 1:
            other_image_dirs[str(p.parent.relative_to(root))] += 1
            continue
        if p.stem in images:
            raise ValueError(f"Ambiguous image stem: {p.stem}")
        images[p.stem] = (p, splits.pop())
    txt_by_stem = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() == ".txt":
            txt_by_stem.setdefault(p.stem, []).append(p)
    labels, owners = {}, {}
    for stem in images:
        candidates = {stem, "gt_" + stem}
        match = re.fullmatch(r"im([0-9]+)", stem)
        if match:
            candidates.add("gt_" + str(int(match.group(1))))
        found = {p for key in candidates for p in txt_by_stem.get(key, [])}
        if len(found) > 1:
            raise ValueError(f"Ambiguous annotation for {stem}: {sorted(map(str, found))}")
        if found:
            label = found.pop()
            if label in owners:
                raise ValueError(f"Annotation reused by {owners[label]} and {stem}: {label}")
            owners[label] = stem
            labels[stem] = label
    split_counts = dict(Counter(s for _, s in images.values()))
    diagnostics = {
        "root": str(root),
        "recognized_images": len(images),
        "matched_labels": len(labels),
        "official_split_counts": split_counts,
        "ignored_recognition_crops": ignored_crops,
        "unrecognized_image_directories": dict(other_image_dirs),
    }
    if not images or set(labels) != set(images):
        raise ValueError(
            "VinText layout or labels incomplete: "
            + json.dumps(
                {
                    **diagnostics,
                    "missing_label_examples": sorted(set(images) - set(labels))[:10],
                    "file_examples": [
                        str(p.relative_to(root)) for p in sorted(root.rglob("*")) if p.is_file()
                    ][:30],
                    "txt_stem_examples": sorted(txt_by_stem)[:10],
                },
                ensure_ascii=False,
            )
        )
    available = set(split_counts)
    if not {"train", "test"}.issubset(available) or not available.intersection(
        {"unseen_test", "dataset_val"}
    ):
        raise ValueError("Missing official split: " + json.dumps(diagnostics, ensure_ascii=False))
    print("VinText source discovery:", json.dumps(diagnostics, ensure_ascii=False))
    return images, labels


def prepare(root, out, vocab, seed=2026):
    root, out = Path(root), Path(out)
    if out.exists():
        raise ValueError("Choose new preparation folder; existing output is never overwritten")
    images, labels = discover(root)
    out.mkdir(parents=True)
    (out / "crops").mkdir()
    rows, rejected, provenance, pixel_splits = [], [], [], {}
    started = last_report = time.monotonic()
    print(
        f"Preparing {len(images)} source images -> {out}; CPU crop/PNG and disk I/O, not GPU training",
        flush=True,
    )
    for image_index, (stem, (path, official)) in enumerate(images.items(), 1):
        with Image.open(path) as source:
            rgb = np.array(source.convert("RGB"))
        pixel = hashlib.sha256(str(rgb.shape).encode() + rgb.tobytes()).hexdigest()
        if pixel in pixel_splits and pixel_splits[pixel] != official:
            raise ValueError("Identical source image crosses official splits")
        pixel_splits[pixel] = official
        # Hold out whole source-image pixel groups from training, never individual crops.
        split = (
            "valid"
            if official == "train"
            and int(hashlib.sha256(f"{seed}:{pixel}".encode()).hexdigest()[:8], 16) % 10 == 0
            else official
        )
        provenance.append(
            {
                "image": str(path.relative_to(root)),
                "image_sha256": digest(path),
                "annotation": str(labels[stem].relative_to(root)),
                "annotation_sha256": digest(labels[stem]),
                "official_split": official,
                "split": split,
                "pixel_sha256": pixel,
            }
        )
        for index, line in enumerate(labels[stem].read_text(encoding="utf-8-sig").splitlines()):
            now = time.monotonic()
            if now - last_report >= 10:
                print(
                    f"Preparing image {image_index}/{len(images)} ({path.name}), "
                    f"line {index + 1}; crops={len(rows)}, rejected={len(rejected)}, "
                    f"elapsed={now - started:.0f}s",
                    flush=True,
                )
                last_report = now
            if not line.strip():
                continue
            try:
                points, text = annotation(line)
                if text in {"", "###", "***"}:
                    raise ValueError("Ignored/unreadable transcript")
                if (
                    any(c not in vocab for c in text)
                    or len(text) > 120
                    or any(c in text for c in "\t\r\n")
                ):
                    raise ValueError("Unsupported vocabulary or transcript length")
                crop = rectify(rgb, points)
            except ValueError as exc:
                rejected.append(
                    {"image": str(path.relative_to(root)), "line": index + 1, "reason": str(exc)}
                )
                continue
            uid = hashlib.sha256(f"{pixel}:{index}:{text}".encode()).hexdigest()[:24]
            target = out / "crops" / f"{uid}.png"
            # Hash encoded bytes in memory instead of reading each PNG back from Drive.
            buffer = io.BytesIO()
            Image.fromarray(crop).save(buffer, format="PNG")
            encoded = buffer.getvalue()
            target.write_bytes(encoded)
            rows.append(
                {
                    "crop": f"crops/{uid}.png",
                    "crop_sha256": hashlib.sha256(encoded).hexdigest(),
                    "text": text,
                    "split": split,
                    "source_pixel_sha256": pixel,
                }
            )
    counts = Counter(r["split"] for r in rows)
    print(f"Crops complete: {dict(counts)}; writing manifest/audit...", flush=True)
    expected = {s for _, s in images.values()} | {"valid"}
    if set(counts) != expected:
        raise ValueError("Empty split after filtering; inspect annotations")
    (out / "manifest.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "audit.json").write_text(
        json.dumps(
            {
                "counts": dict(counts),
                "rejected": rejected,
                "sources": provenance,
                "seed": seed,
                "scope": "Recognition crops, original TXT format; valid held out from official train by source pixels; scene/near-duplicate leakage not audited",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return dict(counts)
