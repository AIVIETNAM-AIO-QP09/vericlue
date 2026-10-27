"""Sinh khóa token và cặp Ed25519 cục bộ; không ghi đè hoặc in bí mật.

    uv run python scripts/gen_keys.py
    uv run python scripts/gen_keys.py --out secrets/server-signing-next

Khóa tạo ra chưa được tự áp dụng vào API; cấu hình môi trường rồi khởi động lại.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))
from vericlue_api.core.signing import load_private_key, load_public_key, public_key_fingerprint  # noqa: E402


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(raw)


def generate(directory: Path) -> str:
    """Create one bundle, or validate/reuse the complete existing bundle unchanged."""
    if directory.is_symlink() or directory.is_junction():
        raise ValueError("Thư mục khóa không phù hợp.")
    private = directory / "ed25519-private.pem"
    public = directory / "ed25519-public.pem"
    token = directory / "session-signing-secret.txt"
    if directory.exists():
        if any(p.is_symlink() or not p.is_file() for p in (private, public, token)):
            raise ValueError("Bộ khóa chưa đầy đủ; hãy chọn thư mục mới, không tự ghi đè.")
        key = load_private_key(private)
        if key.public_key().public_bytes_raw() != load_public_key(public).public_bytes_raw():
            raise ValueError("Khóa công khai không khớp; không tự ghi đè.")
        if token.stat().st_size > 128:
            raise ValueError("Khóa token không phù hợp.")
        secret = token.read_text(encoding="ascii").strip()
        if len(secret) != 64 or any(c not in "0123456789abcdef" for c in secret):
            raise ValueError("Khóa token không phù hợp.")
        return public_key_fingerprint(key.public_key())
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(mode=0o700)  # Atomic exclusive claim; never replace an existing bundle.
    key = Ed25519PrivateKey.generate()
    _write_new(
        private,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    _write_new(
        public,
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )
    _write_new(token, (secrets.token_hex(32) + "\n").encode("ascii"))
    return public_key_fingerprint(key.public_key())


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "secrets/server-signing")
    args = parser.parse_args(argv)
    try:
        fingerprint = generate(args.out.absolute())
    except Exception:
        # Key/parser exceptions may embed file contents; print only a neutral failure.
        print(
            "Không tạo/kiểm tra được bộ khóa. Không ghi đè khóa hiện có; hãy kiểm tra thư mục.",
            file=sys.stderr,
        )
        return 1
    print(f"Bộ khóa sẵn sàng: {args.out.absolute()}")
    print(f"Dấu vân tay khóa công khai (SHA-256 SPKI): {fingerprint}")
    print(
        "Bí mật không được in hoặc tự áp dụng. Đọc hướng dẫn signed-session-results.md trước cấu hình API."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
