"""Small valid images for HTTP tests; no face or identity data."""

import hashlib
import io

from PIL import Image


def synthetic_image(label: bytes = b"synthetic") -> bytes:
    """Make a deterministic lossless PNG so byte-comparison tests stay meaningful."""
    color = tuple(hashlib.sha256(label).digest()[:3])
    out = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(out, format="PNG")
    return out.getvalue()
