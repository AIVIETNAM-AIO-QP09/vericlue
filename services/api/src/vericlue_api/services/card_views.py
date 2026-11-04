"""Bounded, same-photo views for dense QR; never synthesize text or portrait evidence."""

import cv2
import numpy as np


def rectified_card_views(image: np.ndarray) -> list[np.ndarray]:
    """Find up to two large convex card outlines and undo their perspective for QR decoding."""
    height, width = image.shape[:2]
    scale = min(1.0, 960 / max(height, width))
    small = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    views = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        if cv2.contourArea(contour) < small.shape[0] * small.shape[1] * 0.20:
            continue
        quad = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(quad) != 4 or not cv2.isContourConvex(quad):
            continue
        points = quad[:, 0].astype(np.float32) / scale
        # Keep the contour's cyclic order, starting from its upper-left-most corner.
        points = np.roll(points, -np.argmin(points.sum(axis=1)), axis=0)
        if cv2.contourArea(points, oriented=True) < 0:
            points = points[[0, 3, 2, 1]]
        top, right, bottom, left = np.linalg.norm(points - np.roll(points, -1, axis=0), axis=1)
        out_w, out_h = max(top, bottom), max(left, right)
        if min(out_w, out_h) < 120 or not 1.2 <= max(out_w, out_h) / min(out_w, out_h) <= 2.2:
            continue
        shrink = min(1.0, 2560 / max(out_w, out_h))
        out_w, out_h = round(out_w * shrink), round(out_h * shrink)
        target = np.array(
            [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], np.float32
        )
        transform = cv2.getPerspectiveTransform(points, target)
        views.append(cv2.warpPerspective(image, transform, (out_w, out_h)))
        if len(views) == 2:
            break
    return views
