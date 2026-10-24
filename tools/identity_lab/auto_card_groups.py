"""Provisional OCR grouping for experiments; never verified identity labels."""

import csv
import hashlib
import hmac
import json
import math
import re
import secrets
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

VERSION = "easyocr-id-v1"


def accepted_id(readings):
    """Require both views to agree on twelve digits, without character fixes."""
    if len(readings) != 2:
        return None
    texts = [re.sub(r"\s+", "", text) for text, _ in readings]
    if (
        texts[0] == texts[1]
        and re.fullmatch(r"[0-9]{12}", texts[0])
        and len(set(texts[0])) > 1
        and all(score >= 0.85 for _, score in readings)
    ):
        return texts[0]
    return None


def read_id(reader, root, row):
    boxes = [box for box in row["boxes"] if box["field"] == "id"]
    if len(boxes) != 1:
        return None
    x1, y1, x2, y2 = boxes[0]["xyxy"]
    with Image.open(Path(root) / row["image"]) as image:
        crop = image.convert("RGB").crop(
            (math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2))
        )
    if min(crop.size) < 2:
        return None
    crop = crop.resize((max(1, round(crop.width * 64 / crop.height)), 64), Image.Resampling.LANCZOS)
    readings = []
    for variant in (
        crop,
        ImageOps.expand(ImageOps.autocontrast(crop.convert("L")), border=8, fill=255),
    ):
        result = reader.recognize(np.asarray(variant), detail=1, paragraph=False)
        if len(result) != 1:
            return None
        readings.append((result[0][1], float(result[0][2])))
    return accepted_id(readings)


def resolve(rows, tokens):
    """Propagate exact-pixel matches only; quarantine conflicting duplicates."""
    pixels = defaultdict(list)
    for row in rows:
        pixels[row["pixel_sha256"]].append(row)
    assigned, excluded = [], []
    for members in pixels.values():
        values = {tokens[r["image"]] for r in members if tokens.get(r["image"])}
        for row in members:
            if len(values) == 1:
                assigned.append(
                    {
                        **row,
                        "group_id": next(iter(values)),
                        "group_source": VERSION,
                        "person_split_verified": False,
                    }
                )
            else:
                excluded.append(
                    {
                        "image": row["image"],
                        "reason": "conflicting_ids" if values else "id_unreadable_or_uncertain",
                    }
                )
    return sorted(assigned, key=lambda r: r["image"]), excluded


def auto_group(root, rows, out, reader):
    """Cache per-image evidence and export a separate CSV, preserving manual work."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    key_path = out / "grouping.key"
    if not key_path.exists():
        key_path.write_bytes(secrets.token_bytes(32))
    key = key_path.read_bytes()
    cache_path = out / "auto_group_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    tokens = {}
    for i, row in enumerate(rows):
        cache_key = hashlib.sha256(
            json.dumps(
                [VERSION, row["sha256"], row["label_sha256"], hashlib.sha256(key).hexdigest()]
            ).encode()
        ).hexdigest()
        if cache_key not in cache:
            number = read_id(reader, root, row)
            token = (
                "auto_" + hmac.new(key, number.encode(), hashlib.sha256).hexdigest()
                if number
                else None
            )
            cache[cache_key] = token
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(cache), encoding="utf-8")
            temporary.replace(cache_path)
        tokens[row["image"]] = cache[cache_key]
        if (i + 1) % 25 == 0 or i + 1 == len(rows):
            print(f"Auto grouping: {i + 1}/{len(rows)}", flush=True)
    accepted, excluded = resolve(rows, tokens)
    destination = out / "groups_auto.csv"
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["image", "group_id"])
        writer.writeheader()
        writer.writerows({k: row[k] for k in writer.fieldnames} for row in accepted)
    report = {
        "method": VERSION,
        "total": len(rows),
        "included": len(accepted),
        "excluded": len(excluded),
        "groups": len({r["group_id"] for r in accepted}),
        "person_split_verified": False,
        "limitation": "Repeated same-model OCR is not independent verification. Metrics describe only the automatically readable subset; identity leakage remains possible.",
    }
    (out / "auto_group_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "auto_group_excluded.json").write_text(json.dumps(excluded, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return accepted, destination
