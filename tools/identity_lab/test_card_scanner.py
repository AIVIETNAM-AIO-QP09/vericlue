import numpy as np
from card_scanner import CardScanner


def test_valid_qr_avoids_ocr_weights(monkeypatch):
    monkeypatch.setattr(
        "card_scanner.decode_image", lambda _: np.zeros((100, 100, 3), dtype=np.uint8)
    )
    qr = "001099012345||Test Person|01011995|Nam|Test Address|15062021"
    scanner = CardScanner()
    monkeypatch.setattr(scanner, "qr_values", lambda _: [qr])
    monkeypatch.setattr(
        scanner, "_load", lambda: (_ for _ in ()).throw(AssertionError("OCR must not load"))
    )
    assert scanner.scan(b"front", b"back") == {"qr_values": [qr], "fields": {}}
