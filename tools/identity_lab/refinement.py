"""Bounded field re-reading using recognizer word locations, not fixed card coordinates."""

import re
from collections import Counter

import cv2
import numpy as np
from debug_images import crop_line
from fields import DATE, value_for
from PIL import Image


def value_polygon(line, key):
    words = line.get("words", [])
    regions = line.get("word_regions", [])
    if not words or len(words) != len(regions):
        return None
    joined = "".join(words)
    if key.startswith("date_"):
        match = DATE.search(joined)
    else:
        pattern = {
            "nationality": r"nationality[\s:./]*",
            "place_of_residence": r"residence[\s:./]*",
        }.get(key)
        match = re.search(pattern, joined, re.I) if pattern else None
    if match is None:
        return None
    start = match.start() if key.startswith("date_") else match.end()
    offset = 0
    first = None
    for i, word in enumerate(words):
        if offset + len(word) > start:
            first = i
            break
        offset += len(word)
    if first is None:
        return None
    # Word boxes are approximate. Use line top/bottom to retain accents and slope.
    points = np.asarray(line["polygon"], dtype=np.float32)
    x0, x1 = points[:, 0].min(), points[:, 0].max()
    word_left = min(p[0] for p in regions[first])
    t = float(np.clip((word_left - x0) / max(1, x1 - x0), 0, 1))
    t = max(0, t - 0.015)
    if t > 0.95:
        return None
    top = points[0] + t * (points[1] - points[0])
    bottom = points[3] + t * (points[2] - points[3])
    return [top.tolist(), points[1].tolist(), points[2].tolist(), bottom.tolist()]


def choose_reread(field, key, evidence):
    """Repeated agreement is a suggestion, never independent model verification."""
    field["rereads"] = evidence
    votes = Counter()
    for item in evidence:
        if item["confidence"] < 0.7:
            continue
        values = value_for(item["text"], key) if key.startswith("date_") else [item["text"].strip()]
        if len(values) == 1 and values[0]:
            votes[values[0]] += 1
    winners = [value for value, count in votes.items() if count >= 2]
    field["original_value"] = field["value"]
    if len(winners) == 1:
        value = winners[0]
        if value not in field["candidates"]:
            field["candidates"].append(value)
        if value != field["value"]:
            field["value"] = value
            field["reasons"].append("REREAD_SUGGESTION_NOT_VERIFIED")
    else:
        field["reasons"].append("REREADS_UNSTABLE")
    # Never upgrade review based on repeated runs of the same model.
    field["status"] = "review"


def refine_fields(image, lines, fields, predictor):
    for key in ["date_of_expiry", "nationality", "place_of_residence"]:
        field = fields[key]
        if field["status"] != "review" or not field["source_line_ids"]:
            continue
        index = field["source_line_ids"][0]
        polygon = value_polygon(lines[index], key)
        if polygon is None:
            continue
        crop = crop_line(image, polygon)
        evidence = []
        for pad in [0, 0.1, 0.2]:
            border = round(crop.shape[0] * pad)
            variant = cv2.copyMakeBorder(crop, border, border, border, border, cv2.BORDER_REPLICATE)
            text, probability = predictor.predict(
                Image.fromarray(cv2.cvtColor(variant, cv2.COLOR_BGR2RGB)), return_prob=True
            )
            if key == "place_of_residence":
                tail = [lines[j]["text"] for j in field["source_line_ids"][1:]]
                text = ", ".join([text, *tail])
            evidence.append(
                {
                    "text": str(text),
                    "confidence": float(probability) if np.isfinite(probability) else 0.0,
                    "padding_ratio": pad,
                    "polygon": polygon,
                    "source_line_id": index,
                }
            )
        choose_reread(field, key, evidence)
    birth, expiry = fields["date_of_birth"], fields["date_of_expiry"]
    if (
        birth["value"]
        and expiry["value"]
        and expiry["value"] <= birth["value"]
        and "EXPIRY_NOT_AFTER_BIRTH" not in expiry["reasons"]
    ):
        expiry["reasons"].append("EXPIRY_NOT_AFTER_BIRTH")
