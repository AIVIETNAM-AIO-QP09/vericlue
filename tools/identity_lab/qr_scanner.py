"""Compatibility import for historical lab scripts; the scanner belongs to the API."""

from vericlue_api.services.card_scanner import (  # noqa: F401
    MAX_BYTES,
    CardScanner,
    InputError,
    decode_image,
    valid_card_qr,
)
