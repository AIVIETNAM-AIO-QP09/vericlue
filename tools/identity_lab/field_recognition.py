"""Bounded field rereads, with explicit evidence rather than character repair."""

import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime

from PIL import Image, ImageOps


def normalized_value(field, text):
    text = " ".join(unicodedata.normalize("NFC", text).split())
    if field in {"dob", "expire_date"}:
        if not re.fullmatch(r"\d{2}[/-]\d{2}[/-]\d{4}", text):
            return None
        try:
            return datetime.strptime(text.replace("-", "/"), "%d/%m/%Y").date().isoformat()
        except ValueError:
            return None
    if field == "id":
        return text if re.fullmatch(r"[0-9]{12}", text) else None
    return text or None


def select_reading(field, readings):
    votes = defaultdict(list)
    for reading in readings:
        value = normalized_value(field, reading["text"])
        reading["normalized_value"] = value
        if value and reading["confidence"] >= 0.6:
            votes[value].append(reading)
    ranked = sorted(
        votes.items(),
        key=lambda item: (len(item[1]), sum(r["confidence"] for r in item[1])),
        reverse=True,
    )
    initial = readings[0]
    chosen = initial if normalized_value(field, initial["text"]) else None
    suggestion = None
    reasons = ["SAME_MODEL_REREADS_NOT_INDEPENDENT_VERIFICATION"]
    # Require a unique lead and two observations; do not fix a malformed date by regex.
    if (
        ranked
        and len(ranked[0][1]) >= 2
        and (len(ranked) == 1 or len(ranked[0][1]) > len(ranked[1][1]))
    ):
        suggestion = max(ranked[0][1], key=lambda r: r["confidence"])
        if chosen is None:
            chosen = suggestion
    elif chosen is None:
        reasons.append("NO_STABLE_VALID_READING")
    if len({r["text"] for r in readings}) > 1:
        reasons.append("READINGS_DISAGREE")
    if any(r["normalized_value"] is None for r in readings):
        reasons.append("INVALID_FORMAT_CANDIDATE")
    return {
        "text": chosen["text"] if chosen else None,
        "normalized_value": chosen["normalized_value"] if chosen else None,
        "recognition_score": chosen["confidence"] if chosen else None,
        "selected_variant": chosen["variant"] if chosen else None,
        "original_text": initial["text"],
        "suggested_text": suggestion["text"]
        if suggestion and (chosen is None or suggestion["text"] != chosen["text"])
        else None,
        "status": "review",
        "reasons": reasons,
        "readings": readings,
    }


def recognize_field(image, box, field, reader, directory, prefix):
    x1, y1, x2, y2 = box
    height = y2 - y1
    expanded = (
        max(0, math.floor(x1 - height * 0.25)),
        max(0, math.floor(y1 - height * 0.08)),
        min(image.width, math.ceil(x2 + height * 0.25)),
        min(image.height, math.ceil(y2 + height * 0.08)),
    )
    raw = image.crop(box)
    wide = image.crop(expanded)
    border = max(2, round(wide.height * 0.1))
    # Replicate edge pixels rather than adding a high-contrast black border.
    import numpy as np

    padded = Image.fromarray(
        np.pad(np.asarray(wide), ((border, border), (border, border), (0, 0)), mode="edge")
    )
    variants = [
        ("raw", raw),
        ("expanded", wide),
        ("padded", padded),
        ("gray", ImageOps.autocontrast(wide.convert("L")).convert("RGB")),
    ]
    # Avoid speculative rotation: it damaged Vietnamese accents in local probes.
    for fraction in (0.05, 0.2):
        pad = max(2, round(wide.height * fraction))
        bordered = Image.fromarray(
            np.pad(np.asarray(wide), ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        )
        variants.append((f"border_{fraction}", bordered))
    variants.append(("padded_gray", ImageOps.autocontrast(padded.convert("L")).convert("RGB")))
    readings = []
    for name, crop in variants:
        filename = f"{prefix}_{name}.png"
        if directory is not None:
            crop.save(directory / filename)
        text, confidence = reader.predict(crop, return_prob=True)
        confidence = float(confidence)
        readings.append(
            {
                "variant": name,
                "text": str(text),
                "confidence": confidence if math.isfinite(confidence) else 0.0,
                "crop": filename,
                "source_box": list(box if name == "raw" else expanded),
            }
        )
    return select_reading(field, readings)
