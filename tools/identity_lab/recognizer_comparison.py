"""Model agreement is evidence, not identity verification or calibrated confidence."""

import math

from field_recognition import normalized_value


def compare_readers(field, primary, secondary_text, secondary_confidence):
    secondary_confidence = float(secondary_confidence)
    if not math.isfinite(secondary_confidence):
        secondary_confidence = 0.0
    first = normalized_value(field, primary.get("text") or "")
    second = normalized_value(field, secondary_text)
    agreed = bool(
        first
        and first == second
        and (primary.get("recognition_score") or 0) >= 0.6
        and secondary_confidence >= 0.6
    )
    return {
        "candidate_text": primary.get("text"),
        "comparison_text": secondary_text,
        "comparison_confidence": secondary_confidence,
        "value": first if agreed else None,
        "agreement": "agree" if agreed else "unresolved",
        "status": "review",
        "reason": "UNCALIBRATED_MODEL_AGREEMENT"
        if agreed
        else "MODEL_DISAGREEMENT_OR_LOW_CONFIDENCE",
    }
