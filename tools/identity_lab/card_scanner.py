"""Compatibility import for the QR-only card scanner; no OCR fallback."""

from qr_scanner import CardScanner

__all__ = ["CardScanner"]
