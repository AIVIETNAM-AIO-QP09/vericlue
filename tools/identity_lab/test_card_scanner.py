import numpy as np
import pytest
from qr_scanner import CardScanner, InputError

QR = "001099012345||Test Person|01011995|Nam|Test Address|15062021"


def test_valid_qr_uses_no_ocr(monkeypatch):
    monkeypatch.setattr(
        "qr_scanner.decode_image", lambda _: np.zeros((100, 100, 3), dtype=np.uint8)
    )
    scanner = CardScanner(portrait_check=lambda _: True)
    monkeypatch.setattr(scanner, "qr_values", lambda _: [QR])
    assert scanner.scan(b"front") == {"qr_values": [QR], "portrait_usable": True}
    assert not hasattr(scanner, "reader")


def test_missing_qr_never_falls_back_to_text(monkeypatch):
    monkeypatch.setattr(
        "qr_scanner.decode_image", lambda _: np.zeros((100, 100, 3), dtype=np.uint8)
    )

    def forbidden(_):
        raise AssertionError("No QR: must not run portrait or OCR")

    scanner = CardScanner(portrait_check=forbidden)
    monkeypatch.setattr(scanner, "qr_values", lambda _: [])
    assert scanner.scan(b"front", b"back") == {"qr_values": [], "portrait_usable": False}


def test_conflicting_qr_candidates_are_preserved_for_api_validation(monkeypatch):
    monkeypatch.setattr(
        "qr_scanner.decode_image", lambda _: np.zeros((100, 100, 3), dtype=np.uint8)
    )
    scanner = CardScanner(portrait_check=lambda _: True)
    values = [QR, QR.replace("001099012345", "001099999999")]
    monkeypatch.setattr(scanner, "qr_values", lambda _: values)
    assert scanner.scan(b"front", b"back")["qr_values"] == values


def test_invalid_image_is_not_accepted():
    with pytest.raises(InputError):
        CardScanner().scan(b"not an image")
