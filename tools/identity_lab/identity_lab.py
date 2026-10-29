"""Standalone research baseline; no eKYC approval or production router decisions."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from debug_images import crop_line, save_debug
from fields import extract_fields
from PIL import Image, ImageOps, UnidentifiedImageError
from refinement import refine_fields

ROOT = Path(__file__).resolve().parent
MODEL_ROOT = Path(os.environ.get("IDENTITY_MODELS_DIR", str(ROOT / "models")))
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(MODEL_ROOT / "paddlex"))
os.environ.setdefault("HF_HOME", str(MODEL_ROOT / "huggingface"))
os.environ.setdefault("UNIFACE_CACHE_DIR", str(MODEL_ROOT / "uniface"))
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000
OCR_REC_MODEL = os.environ.get("OCR_REC_MODEL", "latin_PP-OCRv5_mobile_rec")
OCR_BACKEND = os.environ.get("OCR_BACKEND", "vietocr")


class InputError(ValueError):
    """Recoverable input error with a stable machine-readable code."""


def decode_image(data: bytes) -> np.ndarray:
    if not data or len(data) > MAX_BYTES:
        raise InputError("E_FILE_SIZE")
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.width * source.height > MAX_PIXELS:
                raise InputError("E_IMAGE_SIZE")
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise InputError("E_IMAGE_FORMAT")
            rgb = np.array(ImageOps.exif_transpose(source).convert("RGB"))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InputError("E_DECODE") from exc
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if not np.isfinite(denominator) or denominator <= 0:
        raise RuntimeError("Invalid embedding norm")
    score = float(np.dot(a, b) / denominator)
    if not np.isfinite(score):
        raise RuntimeError("Invalid similarity")
    return float(np.clip(score, -1, 1))


def field_candidates(lines: list[dict]) -> dict:
    """Conservative candidates, not verified identity or a layout-aware parser."""
    text = "\n".join(line["text"] for line in lines)
    ids = list(dict.fromkeys(re.findall(r"(?<!\d)\d{12}(?!\d)", text)))
    dates = list(dict.fromkeys(re.findall(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", text)))
    return {"id_number_candidates": ids, "date_candidates": dates}


class IdentityLab:
    """Lazy, cached models; lock prevents concurrent inference on shared sessions."""

    def __init__(self, face_model=None):
        self.face_model = face_model or os.environ.get("FACE_RECOGNIZER", "adaface_ir18")
        if self.face_model not in {"adaface_ir18", "arcface_r50"}:
            raise ValueError("Unsupported FACE_RECOGNIZER")
        self._ocr = None
        self._vietocr = None
        self._detector = None
        self._recognizer = None
        self._lock = threading.RLock()

    def _load_ocr(self):
        if OCR_BACKEND not in {"vietocr", "paddle"}:
            raise ValueError("OCR_BACKEND must be vietocr or paddle")
        if OCR_BACKEND == "vietocr" and self._vietocr is None:
            import torch
            from vietocr.tool.config import Cfg
            from vietocr.tool.predictor import Predictor

            config_path = MODEL_ROOT / "vietocr" / "local.yml"
            if not config_path.exists():
                raise RuntimeError("Run prepare_vietocr.py first")
            torch.set_num_threads(4)
            config = Cfg.load_config_from_file(str(config_path))
            config["weights"] = str(MODEL_ROOT / "vietocr" / "vgg_seq2seq.pth")
            self._vietocr = Predictor(config)
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                device="cpu",
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name=OCR_REC_MODEL,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )

    def _load_faces(self):
        if self._detector is None:
            from uniface.constants import ArcFaceWeights
            from uniface.detection import SCRFD
            from uniface.recognition import AdaFace, ArcFace

            detector = SCRFD(providers=["CPUExecutionProvider"])
            recognizer = (
                ArcFace(model_name=ArcFaceWeights.RESNET, providers=["CPUExecutionProvider"])
                if self.face_model == "arcface_r50"
                else AdaFace(providers=["CPUExecutionProvider"])
            )
            # Bound CPU pools: two unconstrained ONNX sessions can oversubscribe laptops.
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            for wrapper, path in (
                (detector, detector._model_path),
                (recognizer, recognizer.model_path),
            ):
                wrapper.session = ort.InferenceSession(
                    str(path), sess_options=options, providers=["CPUExecutionProvider"]
                )
            self._detector, self._recognizer = detector, recognizer

    def ocr(self, data: bytes) -> dict:
        image = decode_image(data)
        started = time.perf_counter()
        with self._lock:
            self._load_ocr()
            result = next(iter(self._ocr.predict(image, return_word_box=True)))
            lines = [
                {
                    "text": str(text),
                    "confidence": float(score),
                    "polygon": np.asarray(poly).tolist(),
                }
                for text, score, poly in zip(
                    result["rec_texts"],
                    result["rec_scores"],
                    result["rec_polys"],
                    strict=True,
                )
            ]
            for line, words, regions in zip(
                lines, result["text_word"], result["text_word_region"], strict=True
            ):
                line["words"] = list(words)
                line["word_regions"] = np.asarray(regions).tolist()
            if self._vietocr is not None:
                for line in lines:
                    line["alternate_text"] = line["text"]
                    line["alternate_confidence"] = line["confidence"]
                    crop = crop_line(image, line["polygon"])
                    text, probability = self._vietocr.predict(
                        Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)),
                        return_prob=True,
                    )
                    line["text"] = str(text)
                    line["confidence"] = float(probability) if np.isfinite(probability) else 0.0
        qr_detector = cv2.QRCodeDetector()
        try:
            found, values, _, _ = qr_detector.detectAndDecodeMulti(image)
            qr = [value for value in values if value] if found else []
        except cv2.error:
            qr = []
        fields = extract_fields(lines)
        if self._vietocr is not None:
            with self._lock:
                refine_fields(image, lines, fields, self._vietocr)
        warnings = ["DOCUMENT_AUTHENTICITY_NOT_CHECKED", "FIELD_EXTRACTION_HEURISTIC"]
        if any(field["status"] != "consistent" for field in fields.values()):
            warnings.append("FIELDS_REQUIRE_REVIEW")
        return {
            "schema_version": "identity-lab/v2",
            "status": "ok" if lines else "retry",
            "reason": None if lines else "E_NO_TEXT",
            "model": "PP-OCRv5_mobile_det+VietOCR_vgg_seq2seq"
            if self._vietocr
            else f"PP-OCRv5_mobile_det+{OCR_REC_MODEL}",
            "lines": lines,
            "fields": fields,
            "document_status": "review" if lines else "retry",
            "coordinate_space": "exif_corrected_input_pixels",
            "candidates": field_candidates(lines),
            "alternate_candidates": field_candidates(
                [{"text": line.get("alternate_text", "")} for line in lines]
            ),
            "qr_payloads": qr,
            "identity_verified": False,
            "warnings": warnings,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    def _face(self, image: np.ndarray, role: str):
        faces = self._detector.detect(image)
        if not faces:
            raise InputError(f"E_NO_FACE_{role}")
        if len(faces) != 1:
            raise InputError(f"E_MULTI_FACE_{role}")
        face = faces[0]
        embedding = self._recognizer.get_normalized_embedding(image, face.landmarks)
        return embedding, np.asarray(face.bbox).tolist()

    def match(self, reference: bytes, selfie: bytes) -> dict:
        ref_image, selfie_image = decode_image(reference), decode_image(selfie)
        started = time.perf_counter()
        with self._lock:
            self._load_faces()
            ref_embedding, ref_box = self._face(ref_image, "REFERENCE")
            selfie_embedding, selfie_box = self._face(selfie_image, "SELFIE")
            similarity = cosine(ref_embedding, selfie_embedding)
        return {
            "schema_version": "identity-lab/v1",
            "status": "ok",
            "model": "SCRFD+AdaFace",
            "cosine_similarity": similarity,
            "decision": "not_calibrated",
            "threshold": None,
            "reference_bbox": ref_box,
            "selfie_bbox": selfie_box,
            "identical_files": hashlib.sha256(reference).digest()
            == hashlib.sha256(selfie).digest(),
            "warnings": [
                "NOT_AN_EKYC_DECISION",
                "PAD_NOT_RUN",
                "THRESHOLD_NOT_CALIBRATED",
            ],
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, help="Optional local JSON output; may contain personal data"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    ocr = commands.add_parser("ocr")
    ocr.add_argument("image", type=Path)
    ocr.add_argument("--debug-dir", type=Path, help="Save sensitive crops locally, opt-in")
    match = commands.add_parser("match")
    match.add_argument("reference", type=Path)
    match.add_argument("selfie", type=Path)
    args = parser.parse_args()
    lab = IdentityLab()
    try:
        if args.command == "ocr":
            data = args.image.read_bytes()
            result = lab.ocr(data)
            if args.debug_dir:
                save_debug(decode_image(data), result["lines"], args.debug_dir, result["fields"])
        else:
            result = lab.match(args.reference.read_bytes(), args.selfie.read_bytes())
    except InputError as exc:
        result = {"status": "retry", "reason": str(exc)}
    except OSError:
        result = {"status": "error", "reason": "E_FILE_IO"}
    except Exception as exc:
        print(f"Model failure: {type(exc).__name__}", file=sys.stderr)
        result = {"status": "error", "reason": "E_MODEL_UNAVAILABLE"}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered)
    if result["status"] != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
