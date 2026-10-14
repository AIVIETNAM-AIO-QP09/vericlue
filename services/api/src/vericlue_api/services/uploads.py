"""Lưu file tải lên vào MEDIA_DIR. Tên file do server đặt, đuôi chỉ lấy từ danh sách cho phép."""

from __future__ import annotations

from pathlib import Path

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
