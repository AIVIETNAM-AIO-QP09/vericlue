"""Bound and canonicalize image bytes before storage or identity inference."""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps

from vericlue_api.core.errors import ApiError

MAX_IMAGE_SIDE = 4096
MAX_IMAGE_PIXELS = 16_000_000
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    suffix: str


def prepare_image(data: bytes) -> PreparedImage:
    """Decode the actual content, apply orientation and remove all ancillary metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                actual_format = source.format
                if (
                    actual_format not in FORMATS
                    or getattr(source, "n_frames", 1) != 1
                    or max(source.size) > MAX_IMAGE_SIDE
                    or source.width * source.height > MAX_IMAGE_PIXELS
                ):
                    raise ValueError("Invalid image bounds or format")
                # Keep the existing storage recipe: RGB conversion and default encoder
                # parameters. Choosing by content prevents a filename-driven bypass.
                pixels = ImageOps.exif_transpose(source).convert("RGB")
                pixels.info.clear()
                output = io.BytesIO()
                pixels.save(output, format=actual_format)
                return PreparedImage(output.getvalue(), FORMATS[actual_format])
    except (
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ApiError(422, "invalid_image", "Ảnh không đọc được. Vui lòng chụp lại.") from exc
