"""Lưu file tải lên vào MEDIA_DIR. Tên file do server đặt, đuôi chỉ lấy từ danh sách cho phép."""

from __future__ import annotations

from fastapi import UploadFile

from vericlue_api.core.errors import ApiError
from vericlue_api.services.storage import save_upload as save_upload


async def read_limited(upload: UploadFile, max_mb: int) -> bytes:
    """Đọc theo khối và dừng sớm (413) nếu vượt giới hạn cấu hình `MAX_UPLOAD_MB`."""
    limit = max_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise ApiError(413, "upload_too_large", f"File vượt quá {max_mb} MB.")
        chunks.append(chunk)
    return b"".join(chunks)
