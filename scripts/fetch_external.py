"""Clone các repo trong external/repos.yaml về external/<name>, đúng commit đã ghim.

Dùng:
  uv run python scripts/fetch_external.py              # tất cả
  uv run python scripts/fetch_external.py --only GenD  # một repo
  uv run python scripts/fetch_external.py --pin        # ghi commit hiện tại vào repos.yaml cho repo còn TODO

Chạy lại nhiều lần không sao: repo đã đúng commit thì bỏ qua.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "external"
MANIFEST = EXTERNAL / "repos.yaml"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def fetch(repo: dict) -> str:
    dest = EXTERNAL / repo["name"]
    commit = str(repo.get("commit", "TODO"))
    if not dest.exists():
        print(f"→ clone {repo['url']}")
        git("clone", "--filter=blob:none", repo["url"], str(dest))
    if commit and commit != "TODO":
        current = git("rev-parse", "HEAD", cwd=dest)
        if current.startswith(commit) or commit.startswith(current):
            print(f"✓ {repo['name']} đã đúng commit {commit[:10]}")
        else:
            git("fetch", "origin", cwd=dest)
            git("checkout", "--detach", commit, cwd=dest)
            print(f"✓ {repo['name']} → {commit[:10]}")
        return commit
    head = git("rev-parse", "HEAD", cwd=dest)
    print(f"! {repo['name']} chưa ghim commit; đang ở {head[:10]} (chạy với --pin để ghim)")
    return head


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--only", help="chỉ tải repo có tên này")
    ap.add_argument(
        "--pin", action="store_true", help="ghi commit hiện tại vào repos.yaml cho repo còn TODO"
    )
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    changed = False
    for repo in data["repos"]:
        if args.only and repo["name"] != args.only:
            continue
        head = fetch(repo)
        if args.pin and str(repo.get("commit", "TODO")) == "TODO":
            repo["commit"] = head
            changed = True
    if changed:
        MANIFEST.write_text(
            "# Repo clone về external/ — commit đã ghim để mọi người chạy giống nhau.\n"
            + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print("Đã ghi commit vào external/repos.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
