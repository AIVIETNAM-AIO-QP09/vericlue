"""Lưu file tải lên vào MEDIA_DIR. Tên file do server đặt, đuôi chỉ lấy từ danh sách cho phép."""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from vericlue_api.core.errors import ApiError

ALLOWED_SUFFIXES = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov", ".wav", ".mp3", ".m4a", ".ogg"}
)


def save_upload(media_dir: str, folder: str, stem: str, filename: str | None, data: bytes) -> Path:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        suffix = ".bin"
    target = Path(media_dir) / folder
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{stem}{suffix}"
    path.write_bytes(data)
    return path


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
