"""QR-only card input: no OCR, no network, no identity or document-authenticity verdict."""

import io
import re
from datetime import datetime
from threading import Lock

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000


class InputError(ValueError):
    """Recoverable invalid image input; messages contain no document data."""


def decode_image(data):
    if not data or len(data) > MAX_BYTES:
        raise InputError("E_FILE_SIZE")
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.width * source.height > MAX_PIXELS:
                raise InputError("E_IMAGE_SIZE")
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise InputError("E_IMAGE_FORMAT")
            rgb = np.array(ImageOps.exif_transpose(source).convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InputError("E_DECODE") from exc


def valid_card_qr(value):
    parts = [part.strip() for part in value.split("|")]
    if len(parts) < 6 or not re.fullmatch(r"[0-9]{12}", parts[0]) or not parts[2]:
        return False
    if parts[4] not in {"Nam", "Nữ"}:
        return False
    try:
        datetime.strptime(parts[3], "%d%m%Y")
    except ValueError:
        return False
    return True


class CardScanner:
    def __init__(self, portrait_check=None):
        self._portrait_check = portrait_check
        self._finder = None
        self._lock = Lock()

    def preload(self):
        """Load only the existing SCRFD portrait finder; never load a text model."""
        import zxingcpp

        if not callable(zxingcpp.read_barcodes):
            raise RuntimeError("QR decoder unavailable")
        if self._portrait_check is not None or self._finder is not None:
            return
        from vericlue_ml.face.pad import ScrfdFaceFinder, _models_root, shared_scrfd_session

        session, _ = shared_scrfd_session(_models_root(None), "cpu")
        self._finder = ScrfdFaceFinder(session, scale=128.0, swap_rb=True)

    @staticmethod
    def qr_values(images):
        values = set()
        try:
            import zxingcpp
        except ImportError:
            zxingcpp = None
        for original in images:
            h, w = original.shape[:2]
            # Preserve the original pixels for dense QR. Work is bounded by decode_image.
            image = original
            if zxingcpp is not None:
                for item in zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode):
                    if getattr(item, "valid", True) and item.text:
                        values.add(item.text)
            # A second decoder also runs, so conflicting codes are not silently ignored.
            for pixels in (
                [image]
                if max(h, w) <= 1600
                else [cv2.resize(image, (round(w * 1600 / max(h, w)), round(h * 1600 / max(h, w))))]
            ):
                detector = cv2.QRCodeDetector()
                try:
                    ok, texts, _, _ = detector.detectAndDecodeMulti(pixels)
                    if ok:
                        values.update(t for t in texts if t)
                except (cv2.error, UnicodeError):
                    pass
                try:
                    text, _, _ = detector.detectAndDecode(pixels)
                    if text:
                        values.add(text)
                except (cv2.error, UnicodeError):
                    pass
        return sorted(values)

    def portrait_usable(self, image):
        if self._portrait_check is not None:
            return bool(self._portrait_check(image))
        with self._lock:
            self.preload()
            faces = self._finder.find(image)
        return bool(
            len(faces) == 1
            and faces[0].landmarks is not None
            and min(faces[0].x2 - faces[0].x1, faces[0].y2 - faces[0].y1) >= 40
        )

    def scan(self, front, back=None):
        images = [decode_image(front)]
        if back is not None:
            images.append(decode_image(back))
        values = self.qr_values(images)
        return {
            "qr_values": values,
            "portrait_usable": (
                self.portrait_usable(images[0]) if any(valid_card_qr(v) for v in values) else False
            ),
        }
