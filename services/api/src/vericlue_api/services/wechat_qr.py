"""Pinned CPU WeChat QR models from OpenCV; no card data leaves the process."""

import hashlib
from pathlib import Path
from threading import Lock

REVISION = "a8b69ccc738421293254aec5ddb38bd523503252"
MODEL_SUBDIR = "wechat-qrcode"
MODEL_SHA256 = {
    "detect.prototxt": "e8acfc395caf443a47f15686a9b9207b36cb8f7e6ceb8fbaf6466665e68a9466",
    "detect.caffemodel": "cc49b8c9babaf45f3037610fe499df38c8819ebda29e90ca9f2e33270f6ef809",
    "sr.prototxt": "8ae41acba97e8b4a8e741ee350481e49b8e01d787193f470a4c95ee1c02d5b61",
    "sr.caffemodel": "e5d36889d8e6ef2f1c1f515f807cec03979320ac81792cd8fb927c31fd658ae3",
}


def verified_model_paths(models_dir: Path) -> list[Path]:
    """Reject missing, modified or redirected weights before native model loading."""
    root = models_dir.resolve()
    paths = []
    for name, expected in MODEL_SHA256.items():
        path = (root / MODEL_SUBDIR / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("WeChat QR model missing or outside MODELS_DIR")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("WeChat QR model checksum mismatch")
        paths.append(path)
    return paths


class WeChatQR:
    """Load once and serialize calls to the native detector/super-resolution pair."""

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self._detector = None
        self._lock = Lock()

    def preload(self) -> None:
        import cv2

        with self._lock:
            if self._detector is None:
                paths = verified_model_paths(self.models_dir)
                self._detector = cv2.wechat_qrcode_WeChatQRCode(*(str(p) for p in paths))

    def decode(self, image) -> set[str]:
        self.preload()
        with self._lock:
            texts, _ = self._detector.detectAndDecode(image)
        return {text for text in texts if text}
