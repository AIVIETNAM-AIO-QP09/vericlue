"""Sinh `packages/contracts/openapi.json` từ ứng dụng FastAPI (không cần chạy server).

    uv run python scripts/gen_openapi.py           # ghi file
    uv run python scripts/gen_openapi.py --check   # báo lỗi nếu file đã commit không khớp code

Web sinh type TypeScript từ file này (`cd apps/web && npm run gen:api`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "packages" / "contracts" / "openapi.json"


def render() -> str:
    sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
    from vericlue_api.main import create_app

    return json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="không ghi, chỉ so với file hiện có")
    args = parser.parse_args()

    text = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} đã cũ: chạy `uv run python scripts/gen_openapi.py`")
            return 1
        print("openapi.json khớp code")
        return 0

    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Đã ghi {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
