"""Explicit local debug export; contains personal data, never enabled by the API."""

import cv2
import numpy as np


def crop_line(image, polygon):
    points = np.asarray(polygon, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Invalid text polygon")
    width = round(max(np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3])))
    height = round(
        max(np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2]))
    )
    if min(width, height) < 2 or max(width, height) > 16000:
        raise ValueError("Invalid text crop dimensions")
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32
    )
    crop = cv2.warpPerspective(
        image,
        cv2.getPerspectiveTransform(points, destination),
        (width, height),
        borderMode=cv2.BORDER_REPLICATE,
    )
    return crop


def save_debug(image, lines, directory, fields=None):
    directory.mkdir(parents=True, exist_ok=True)
    overlay = image.copy()
    for index, line in enumerate(lines):
        poly = np.asarray(line["polygon"], dtype=np.int32)
        cv2.polylines(overlay, [poly], True, (0, 255, 0), 2)
        cv2.putText(
            overlay, str(index), tuple(poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
        )
        ok, encoded = cv2.imencode(".png", crop_line(image, line["polygon"]))
        if not ok:
            raise OSError("Cannot encode debug crop")
        (directory / f"line_{index:03d}.png").write_bytes(encoded.tobytes())
    ok, encoded = cv2.imencode(".png", overlay)
    if not ok:
        raise OSError("Cannot encode overlay")
    (directory / "overlay.png").write_bytes(encoded.tobytes())
    for key, field in (fields or {}).items():
        for index, evidence in enumerate(field.get("rereads", [])):
            crop = crop_line(image, evidence["polygon"])
            border = round(crop.shape[0] * evidence["padding_ratio"])
            crop = cv2.copyMakeBorder(crop, border, border, border, border, cv2.BORDER_REPLICATE)
            ok, encoded = cv2.imencode(".png", crop)
            if not ok:
                raise OSError("Cannot encode field crop")
            (directory / f"field_{key}_{index}.png").write_bytes(encoded.tobytes())
