"""Pairwise face verification research API; no threshold or liveness decision."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
from identity_lab import IdentityLab, InputError, cosine, decode_image

EMBEDDING_MODES = ("single", "flip_mean")


def pipeline_config(lab, embedding_mode="single"):
    """Bind calibration to weights, preprocessing implementation and runtime."""
    from importlib.metadata import version

    from card_dataset import sha256

    if embedding_mode not in EMBEDDING_MODES:
        raise InputError("E_EMBEDDING_MODE")
    return {
        "implementation_sha256": sha256(Path(__file__)),
        "loader_sha256": sha256(Path(__file__).with_name("identity_lab.py")),
        "detector_sha256": sha256(lab._detector._model_path),
        "recognizer_sha256": sha256(lab._recognizer.model_path),
        "embedding_mode": embedding_mode,
        "recognizer": lab.face_model,
        "detection_threshold": float(lab._detector.confidence_threshold),
        "nms_threshold": float(lab._detector.nms_threshold),
        "versions": {
            n: version(n)
            for n in ("uniface", "onnxruntime", "numpy", "opencv-python", "scikit-image")
        },
    }


def pixel_hash(image):
    return hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()


def reference_crop(image, roi):
    """Explicit portrait region, coordinates after EXIF correction; never auto-select a face."""
    if roi is None:
        return image, [0, 0]
    if not isinstance(roi, (list, tuple)) or len(roi) != 4 or any(type(v) is not int for v in roi):
        raise InputError("E_REFERENCE_ROI")
    x1, y1, x2, y2 = roi
    h, w = image.shape[:2]
    if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h) or min(x2 - x1, y2 - y1) < 32:
        raise InputError("E_REFERENCE_ROI")
    return image[y1:y2, x1:x2], [x1, y1]


def face_embedding(recognizer, aligned, mode="single"):
    if mode not in EMBEDDING_MODES:
        raise InputError("E_EMBEDDING_MODE")

    def unit(image):
        vector = np.asarray(recognizer.get_embedding(image), dtype=np.float64).ravel()
        norm = np.linalg.norm(vector)
        if (
            vector.size == 0
            or not np.isfinite(vector).all()
            or not np.isfinite(norm)
            or norm <= 1e-12
        ):
            raise RuntimeError("Invalid embedding")
        return vector / norm

    vector = unit(aligned)
    if mode == "flip_mean":
        flipped = unit(np.ascontiguousarray(aligned[:, ::-1]))
        if vector.shape != flipped.shape:
            raise RuntimeError("Embedding dimensions differ")
        vector = vector + flipped
        norm = np.linalg.norm(vector)
        if norm <= 1e-12:
            raise RuntimeError("Degenerate flip embedding")
        vector /= norm
    return vector


def validate_face(face, image, role):
    box = np.asarray(face.bbox, dtype=float)
    points = np.asarray(face.landmarks, dtype=float)
    if not math.isfinite(float(face.confidence)) or not 0 <= float(face.confidence) <= 1:
        raise InputError(f"E_FACE_GEOMETRY_{role}")
    if (
        box.shape != (4,)
        or points.shape != (5, 2)
        or not np.isfinite(box).all()
        or not np.isfinite(points).all()
    ):
        raise InputError(f"E_FACE_GEOMETRY_{role}")
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    if min(x2 - x1, y2 - y1) < 32:
        raise InputError(f"E_FACE_TOO_SMALL_{role}")
    if min(x1, y1) < 0 or x2 > w or y2 > h:
        raise InputError(f"E_FACE_CLIPPED_{role}")
    if (
        (points[:, 0] < 0).any()
        or (points[:, 0] >= w).any()
        or (points[:, 1] < 0).any()
        or (points[:, 1] >= h).any()
    ):
        raise InputError(f"E_FACE_LANDMARKS_{role}")
    eye_distance = float(np.linalg.norm(points[1] - points[0]))
    if eye_distance < 8:
        raise InputError(f"E_FACE_LANDMARKS_{role}")
    # A degenerate layout can produce a plausible-looking but meaningless aligned crop.
    if (
        np.linalg.matrix_rank(points - points.mean(axis=0)) < 2
        or len(np.unique(points, axis=0)) < 5
    ):
        raise InputError(f"E_FACE_LANDMARKS_{role}")
    crop = image[math.floor(y1) : math.ceil(y2), math.floor(x1) : math.ceil(x2)]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Diagnostics only: these are not calibrated accept/reject thresholds.
    quality = {
        "width_pixels": float(x2 - x1),
        "height_pixels": float(y2 - y1),
        "inter_eye_pixels": eye_distance,
        "mean_brightness": float(gray.mean()),
        "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "roll_degrees": math.degrees(
            math.atan2(points[1, 1] - points[0, 1], points[1, 0] - points[0, 0])
        ),
    }
    return {
        "bbox": box.tolist(),
        "landmarks": points.tolist(),
        "detection_score": float(face.confidence),
        "quality": quality,
        "warnings": ["QUALITY_MEASURES_NOT_CALIBRATED"],
    }


def align_face(lab, image, role, debug_dir=None):
    from uniface.face_utils import face_alignment

    faces = lab._detector.detect(image)
    if not faces:
        raise InputError(f"E_NO_FACE_{role}")
    if len(faces) != 1:
        raise InputError(f"E_MULTI_FACE_{role}")
    face = faces[0]
    evidence = validate_face(face, image, role)
    aligned, inverse = face_alignment(image, face.landmarks, image_size=lab._recognizer.input_size)
    if not np.isfinite(inverse).all() or abs(np.linalg.det(inverse[:, :2])) < 1e-12:
        raise InputError(f"E_FACE_ALIGNMENT_{role}")
    mask = cv2.warpAffine(
        np.ones(image.shape[:2], dtype=np.uint8),
        inverse,
        (aligned.shape[1], aligned.shape[0]),
        flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
    )
    evidence["quality"]["alignment_padding_fraction"] = float(np.mean(mask == 0))
    evidence["quality"]["aligned_laplacian_variance"] = float(
        cv2.Laplacian(cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    )
    if np.any(mask == 0):
        evidence["warnings"].append("ALIGNMENT_INCLUDES_PADDING")
    if debug_dir:
        directory = Path(debug_dir)
        directory.mkdir(parents=True, exist_ok=True)
        overlay = image.copy()
        x1, y1, x2, y2 = map(round, evidence["bbox"])
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
        for x, y in evidence["landmarks"]:
            cv2.circle(overlay, (round(x), round(y)), 3, (0, 0, 255), -1)
        for name, array in (
            (f"{role.lower()}_overlay.jpg", overlay),
            (f"{role.lower()}_aligned.png", aligned),
        ):
            ok, encoded = cv2.imencode(Path(name).suffix, array)
            if not ok:
                raise OSError("Cannot encode debug image")
            (directory / name).write_bytes(encoded.tobytes())
    return aligned, evidence


def extract_face(lab, image, role, debug_dir=None, embedding_mode="single"):
    aligned, evidence = align_face(lab, image, role, debug_dir)
    return face_embedding(lab._recognizer, aligned, embedding_mode), evidence


def match_pair(lab, reference, selfie, debug_dir=None, reference_roi=None, embedding_mode="single"):
    started = time.perf_counter()
    ref_image, selfie_image = decode_image(reference), decode_image(selfie)
    identical = ref_image.shape == selfie_image.shape and np.array_equal(ref_image, selfie_image)
    if embedding_mode not in EMBEDDING_MODES:
        raise InputError("E_EMBEDDING_MODE")
    ref_image, offset = reference_crop(ref_image, reference_roi)
    identical = identical or (
        ref_image.shape == selfie_image.shape and np.array_equal(ref_image, selfie_image)
    )
    result = {
        "schema_version": "face-pair-lab/v2",
        "status": "ok",
        "reason": None,
        "decision": "review",
        "identity_verified": False,
        "cosine_similarity": None,
        "threshold": None,
        "model": "SCRFD-10G+"
        + {"adaface_ir18": "AdaFace-IR18", "arcface_r50": "ArcFace-R50"}[lab.face_model],
        "embedding_mode": embedding_mode,
        "reference_roi": reference_roi,
        "coordinate_space": "exif_corrected_input_pixels",
        "reference": None,
        "selfie": None,
        "identical_pixels": identical,
        "warnings": [
            "THRESHOLD_NOT_CALIBRATED",
            "PAD_NOT_RUN",
            "DOCUMENT_AUTHENTICITY_NOT_CHECKED",
        ],
        "elapsed_ms": 0.0,
    }
    try:
        if identical:
            raise InputError("E_IDENTICAL_INPUTS")
        with lab._lock:
            lab._load_faces()
            first, result["reference"] = extract_face(
                lab, ref_image, "REFERENCE", debug_dir, embedding_mode
            )
            if reference_roi is not None:
                evidence = result["reference"]
                evidence["bbox"] = (np.array(evidence["bbox"]) + np.tile(offset, 2)).tolist()
                evidence["landmarks"] = (np.array(evidence["landmarks"]) + offset).tolist()
                evidence["warnings"].append("REFERENCE_ROI_PROVIDED_NOT_DOCUMENT_VERIFIED")
            second, result["selfie"] = extract_face(
                lab, selfie_image, "SELFIE", debug_dir, embedding_mode
            )
            result["cosine_similarity"] = cosine(first, second)
    except InputError as exc:
        result.update(status="retry", decision="retry", reason=str(exc), cosine_similarity=None)
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("selfie", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--debug-dir", type=Path)
    parser.add_argument("--reference-roi", nargs=4, type=int, metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--embedding-mode", choices=EMBEDDING_MODES, default="single")
    parser.add_argument("--recognizer", choices=("adaface_ir18", "arcface_r50"))
    args = parser.parse_args()
    result = match_pair(
        IdentityLab(face_model=args.recognizer),
        args.reference.read_bytes(),
        args.selfie.read_bytes(),
        args.debug_dir,
        args.reference_roi,
        args.embedding_mode,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
