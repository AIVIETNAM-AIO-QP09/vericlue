"""Chuẩn bị file MediaPipe cho trang lab ChromaPulse để chạy OFFLINE (không gọi CDN lúc chạy).

    uv run python scripts/fetch_web_assets.py          # cần chạy `cd apps/web && npm ci` trước
    uv run python scripts/fetch_web_assets.py --check  # chỉ kiểm file đã đủ và đúng hash chưa

Làm hai việc:
  1. chép thư mục wasm của @mediapipe/tasks-vision (Apache-2.0) từ node_modules vào
     apps/web/public/mediapipe/wasm/;
  2. tải face_landmarker.task từ URL cố định, kiểm SHA-256, ghi vào apps/web/public/mediapipe/.

Thư mục apps/web/public/mediapipe/ được gitignore (trọng số mô hình không commit, AGENTS.md §6 luật 5).
Sau này gộp mô hình vào models/manifest.yaml (DATA-02); hiện giữ riêng ở đây để không đụng file đó.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"
TARGET = WEB / "public" / "mediapipe"
WASM_SRC = WEB / "node_modules" / "@mediapipe" / "tasks-vision" / "wasm"

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/"
    "face_landmarker.task"
)
MODEL_NAME = "face_landmarker.task"
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
WASM_FILES = (
    "vision_wasm_internal.js",
    "vision_wasm_internal.wasm",
    "vision_wasm_nosimd_internal.js",
    "vision_wasm_nosimd_internal.wasm",
    "vision_wasm_module_internal.js",
    "vision_wasm_module_internal.wasm",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def missing_files() -> list[str]:
    missing = [f"wasm/{n}" for n in WASM_FILES if not (TARGET / "wasm" / n).is_file()]
    model = TARGET / MODEL_NAME
    if not model.is_file():
        missing.append(MODEL_NAME)
    elif sha256(model) != MODEL_SHA256:
        missing.append(f"{MODEL_NAME} (sai SHA-256)")
    return missing


def copy_wasm() -> None:
    if not WASM_SRC.is_dir():
        raise SystemExit(
            f"Chưa có {WASM_SRC}. Chạy `cd apps/web && npm ci` trước rồi chạy lại script này."
        )
    dest = TARGET / "wasm"
    dest.mkdir(parents=True, exist_ok=True)
    for name in WASM_FILES:
        shutil.copy2(WASM_SRC / name, dest / name)
    print(f"Đã chép {len(WASM_FILES)} file wasm vào {dest.relative_to(ROOT)}")


def download_model() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    dest = TARGET / MODEL_NAME
    if dest.is_file() and sha256(dest) == MODEL_SHA256:
        print(f"{MODEL_NAME} đã có, đúng SHA-256")
        return
    tmp = dest.with_suffix(".part")
    print(f"Tải {MODEL_URL}")
    with urllib.request.urlopen(MODEL_URL, timeout=60) as res, tmp.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(res, out)
    got = sha256(tmp)
    if got != MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"SHA-256 không khớp: nhận {got}, mong đợi {MODEL_SHA256}")
    tmp.replace(dest)
    print(f"Đã ghi {dest.relative_to(ROOT)} ({dest.stat().st_size} byte, SHA-256 khớp)")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="chỉ kiểm, không tải hay chép")
    args = parser.parse_args()

    if args.check:
        missing = missing_files()
        if missing:
            print("Thiếu hoặc sai: " + ", ".join(missing))
            return 1
        print("Đủ file MediaPipe cho chế độ offline")
        return 0

    copy_wasm()
    download_model()
    return 0 if not missing_files() else 1


if __name__ == "__main__":
    raise SystemExit(main())
