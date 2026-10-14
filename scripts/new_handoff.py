"""Tạo file ghi chú bàn giao mới trong docs/status/handoffs/.

Mỗi lần bàn giao là MỘT FILE RIÊNG, nên nhiều người hoặc nhiều AI ghi cùng lúc
cũng không bao giờ bị xung đột khi gộp nhánh.

Dùng:
  uv run python scripts/new_handoff.py --task FACE-02 --who "Quoc+Claude"
  uv run python scripts/new_handoff.py --latest 3      # in 3 bàn giao mới nhất
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFFS = ROOT / "docs" / "status" / "handoffs"
TEMPLATE = ROOT / "docs" / "templates" / "handoff.md"


def slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9-]+", "-", text.strip())
    return text.strip("-").lower() or "x"


def create(task: str, who: str, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    HANDOFFS.mkdir(parents=True, exist_ok=True)
    name = f"{now:%Y-%m-%d-%H%M}-{slug(task)}-{slug(who)}.md"
    path = HANDOFFS / name
    body = TEMPLATE.read_text(encoding="utf-8")
    body = (
        body.replace("{{DATE}}", f"{now:%Y-%m-%d %H:%M}")
        .replace("{{WHO}}", who)
        .replace("{{TASK}}", task.upper())
    )
    path.write_text(body, encoding="utf-8")
    return path


def latest(n: int) -> list[Path]:
    files = sorted(p for p in HANDOFFS.glob("*.md") if p.name != "README.md")
    return files[-n:][::-1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--task", help="mã task, ví dụ FACE-02")
    ap.add_argument("--who", help="tên người và/hoặc AI, ví dụ 'Quoc+Codex'")
    ap.add_argument("--latest", type=int, help="in đường dẫn N bàn giao mới nhất")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.latest:
        for p in latest(args.latest):
            print(p.relative_to(ROOT).as_posix())
        return 0
    if not (args.task and args.who):
        ap.error("cần --task và --who (hoặc --latest N)")
    print(create(args.task, args.who).relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
