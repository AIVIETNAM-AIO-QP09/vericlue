"""RAM-only field scanning for the session API bridge; no identity/authenticity verdict."""

import math
import os
import re
from datetime import datetime
from pathlib import Path
from threading import Lock

import cv2
from card_dataset import FIELDS
from field_recognition import recognize_field
from identity_lab import MODEL_ROOT, decode_image
from PIL import Image


class CardScanner:
    def __init__(self):
        self.lock = Lock()
        self.model = None
        self.reader = None

    def _load(self):
        import torch
        from train_card_detector import build_model
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        if self.model is not None:
            return
        torch.set_num_threads(2)
        path = Path(os.environ["CCCD_DETECTOR_CHECKPOINT"])
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if checkpoint["config"]["fields"] != FIELDS:
            raise ValueError("Detector field order mismatch")
        model = build_model(pretrained=False, image_size=checkpoint["config"]["image_size"])
        model.load_state_dict(checkpoint["model"], strict=True)
        model.eval()
        cfg = Cfg.load_config_from_file(str(MODEL_ROOT / "vietocr/local.yml"))
        cfg["device"] = "cpu"
        cfg["weights"] = str(MODEL_ROOT / "vietocr/vgg_seq2seq.pth")
        cfg["cnn"]["pretrained"] = False
        reader = Predictor(cfg)
        self.model, self.reader = model, reader

    @staticmethod
    def qr_values(images):
        values = set()
        detector = cv2.QRCodeDetector()
        for image in images:
            # Bound QR work while preserving the original for OCR.
            h, w = image.shape[:2]
            scaled = (
                cv2.resize(image, (round(w * 1600 / max(h, w)), round(h * 1600 / max(h, w))))
                if max(h, w) > 1600
                else image
            )
            try:
                ok, texts, _, _ = detector.detectAndDecodeMulti(scaled)
                if ok:
                    values.update(t for t in texts if t)
                text, _, _ = detector.detectAndDecode(scaled)
                if text:
                    values.add(text)
            except cv2.error:
                continue
        return sorted(values)

    def scan(self, front, back):
        import torch
        from torchvision.transforms.functional import to_tensor

        images = [decode_image(front), decode_image(back)]
        qr = self.qr_values(images)
        for text in qr:
            parts = [p.strip() for p in text.split("|")]
            if (
                len(parts) >= 6
                and re.fullmatch(r"[0-9]{12}", parts[0])
                and parts[2]
                and parts[4] in {"Nam", "Nữ"}
            ):
                try:
                    datetime.strptime(parts[3], "%d%m%Y")
                except ValueError:
                    continue
                # Do not require OCR weights when server can parse the QR.
                return {"qr_values": qr, "fields": {}}
        # Only the session backend parses/validates QR fields. Invalid QR may coexist with OCR.
        with self.lock:
            self._load()
            image = Image.fromarray(cv2.cvtColor(images[0], cv2.COLOR_BGR2RGB))
            with torch.inference_mode():
                pred = self.model([to_tensor(image)])[0]
            readings = {}
            for box, label, score in zip(
                pred["boxes"], pred["labels"], pred["scores"], strict=True
            ):
                if float(score) < 0.5:
                    continue
                field = FIELDS[int(label) - 1]
                x1, y1, x2, y2 = box.tolist()
                bounds = (
                    max(0, math.floor(x1)),
                    max(0, math.floor(y1)),
                    min(image.width, math.ceil(x2)),
                    min(image.height, math.ceil(y2)),
                )
                if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                    continue
                item = recognize_field(image, bounds, field, self.reader, None, field)
                readings.setdefault(field, []).append(item["normalized_value"])
            # Ambiguous duplicate detections are left blank for human correction.
            fields = {
                key: values[0] for key, values in readings.items() if len(values) == 1 and values[0]
            }
        return {"qr_values": qr, "fields": fields}
