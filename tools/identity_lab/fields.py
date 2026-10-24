"""Conservative front-card extraction. Never repairs identity characters by guessing."""

import re
import unicodedata
from datetime import datetime

LABELS = {
    "id_number": r"\b(?:so\s*[i1/]?\s*no|no\.)",
    "full_name": r"\b(?:ho va ten|full\s*name)\b",
    "date_of_birth": r"\b(?:ngay sinh|date of birth)\b",
    "sex": r"\b(?:gioi tinh|sex)\b",
    "nationality": r"\b(?:quoc tich|nationality)\b",
    "place_of_origin": r"\b(?:que quan|place of\s*origin)\b",
    "place_of_residence": r"\b(?:noi thuong tru|place of\s*residence)\b",
    "date_of_expiry": r"\b(?:co gia tri den|date of\s*expiry)\b",
}
DATE = re.compile(r"(?<!\d)\d{2}[/-]\d{2}[/-]\d{4}(?!\d)")


def fold(text):
    return (
        "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
        .lower()
        .replace("đ", "d")
    )


def labels(text):
    return [key for key, pattern in LABELS.items() if re.search(pattern, fold(text))]


def bounds(line):
    points = line["polygon"]
    xs, ys = zip(*points, strict=True)
    return min(xs), min(ys), max(xs), max(ys)


def value_for(text, key):
    if key == "id_number":
        return re.findall(r"(?<!\d)\d{12}(?!\d)", text)
    if key.startswith("date_"):
        valid = []
        for item in DATE.findall(text):
            try:
                parsed = datetime.strptime(item.replace("-", "/"), "%d/%m/%Y")
                valid.append(parsed.strftime("%Y-%m-%d"))
            except ValueError:
                pass
        return valid
    if key == "sex":
        text = re.split(r"quốc tịch|nationality", text, flags=re.I)[0]
        return [m.group() for m in re.finditer(r"\b(?:Nam|Nữ|Male|Female)\b", text, re.I)]
    if key == "nationality":
        match = re.search(r"nationality\s*[:./i1-]*\s*(.+)$", text, re.I)
        return [match.group(1).strip()] if match else []
    if key == "place_of_residence":
        match = re.search(r"place\s*of\s*residence\s*[:./]*\s*(.+)$", text, re.I)
        if match:
            return [match.group(1).strip()]
    if not labels(text) and text.strip():
        return [text.strip()]
    return []


def extract_fields(lines):
    output = {}
    for key in LABELS:
        anchors = [
            i
            for i, line in enumerate(lines)
            if key in labels(line["text"]) or key in labels(line.get("alternate_text", ""))
        ]
        choices = []
        for anchor in anchors:
            ax, ay, ar, ab = bounds(lines[anchor])
            height = max(1, ab - ay)
            for i, line in enumerate(lines):
                x, y, right, bottom = bounds(line)
                own_labels = set(labels(line["text"]) + labels(line.get("alternate_text", "")))
                # A merged sex/nationality line can supply both fields.
                if own_labels - {key} and not (key == "sex" and own_labels <= {"nationality"}):
                    continue
                same_row = x >= ar - height and abs((y + bottom - ay - ab) / 2) < height * 0.8
                below = -height * 0.5 <= y - ab <= height * 1.5 and abs(x - ax) < max(
                    height * 2, (ar - ax) * 0.5
                )
                if i != anchor and not (same_row or below):
                    continue
                primary = value_for(line["text"], key)
                alternate = value_for(line.get("alternate_text", ""), key)
                if primary or alternate:
                    distance = (
                        0
                        if i == anchor
                        else (
                            abs(y - ay) + abs(x - ar) * 0.05 if same_row else height + abs(y - ab)
                        )
                    )
                    choices.append((distance, i, primary, alternate))
        choices.sort(key=lambda c: c[0])
        result = {
            "value": None,
            "status": "missing",
            "source_line_ids": [],
            "candidates": [],
            "reasons": ["FIELD_NOT_FOUND"],
        }
        if choices:
            _, index, primary, alternate = choices[0]
            candidate_values = list(dict.fromkeys(primary + alternate))
            # Strict agreement is evidence, never proof of correctness.
            agrees = len(primary) == len(alternate) == 1 and primary == alternate
            result = {
                "value": primary[0]
                if len(primary) == 1
                else alternate[0]
                if not primary and len(alternate) == 1
                else None,
                "status": "consistent" if agrees else "review",
                "source_line_ids": [index],
                "candidates": candidate_values,
                "reasons": [] if agrees else ["READERS_DISAGREE_OR_SINGLE_VALID_SOURCE"],
            }
            if key in {"place_of_origin", "place_of_residence"}:
                result["status"] = "review"
                result["reasons"].append("ADDRESS_COMPLETENESS_UNVERIFIED")
            if key == "place_of_residence":
                # Join only immediately adjacent unlabelled lines in the same column.
                # Keep both readers' complete candidates; never normalize an address by guessing.
                x0, _, _, bottom0 = bounds(lines[index])
                source_ids = [index]
                for j, following in sorted(enumerate(lines), key=lambda pair: bounds(pair[1])[1]):
                    if (
                        j == index
                        or labels(following["text"])
                        or labels(following.get("alternate_text", ""))
                    ):
                        continue
                    x1, y1, _, bottom1 = bounds(following)
                    h1 = max(1, bottom1 - y1)
                    if abs(x1 - x0) < h1 and -0.3 * h1 <= y1 - bottom0 <= h1:
                        primary = [v + ", " + following["text"] for v in primary]
                        alternate = [
                            v + ", " + following.get("alternate_text", "") for v in alternate
                        ]
                        source_ids.append(j)
                        bottom0 = bottom1
                result["source_line_ids"] = source_ids
                result["candidates"] = list(dict.fromkeys(primary + alternate))
                result["value"] = (
                    primary[0]
                    if len(primary) == 1
                    else alternate[0]
                    if len(alternate) == 1
                    else None
                )
            if any(
                lines[index].get(conf, 0) < 0.7 for conf in ["confidence", "alternate_confidence"]
            ):
                result["status"] = "review"
                result["reasons"].append("LOW_CONFIDENCE_HEURISTIC")
            if (
                len(choices) > 1
                and abs(choices[1][0] - choices[0][0]) < 1
                and choices[1][1] != index
            ):
                result["status"] = "review"
                result["reasons"].append("AMBIGUOUS_LAYOUT")
        output[key] = result
    birth, expiry = output["date_of_birth"], output["date_of_expiry"]
    if birth["value"] and expiry["value"] and expiry["value"] <= birth["value"]:
        expiry["status"] = "review"
        expiry["reasons"].append("EXPIRY_NOT_AFTER_BIRTH")
    return output
