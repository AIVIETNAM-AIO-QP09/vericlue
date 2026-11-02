"""Generate the standalone, private Colab data preparation notebook from tested source."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/prepare_nes2net_data.py"
OUTPUT = ROOT / "ml/notebooks/prepare_nes2net_data.ipynb"
REVISION = "33b2a469901cb71b243403254d3cfef25170526c"


def build(source: str, commit: str, *, dirty: bool) -> dict:
    """Embed source/hash and fail before cloud execution when provenance is uncommitted."""
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None or type(dirty) is not bool:
        raise ValueError("Real source commit and explicit dirty state required")
    source = source.replace("\r\n", "\n")
    digest = hashlib.sha256(source.encode()).hexdigest()
    code = f"""# Generated from scripts/prepare_nes2net_data.py; do not edit embedded code.
import hashlib, json, os, runpy
from pathlib import Path
SOURCE_COMMIT = {commit!r}
SOURCE_DIRTY = {dirty!r}
SOURCE_SHA256 = {digest!r}
if SOURCE_DIRTY:
    raise ValueError("Commit preparation source and regenerate notebook before collecting data")
source = {source!r}
if hashlib.sha256(source.encode()).hexdigest() != SOURCE_SHA256:
    raise ValueError("Embedded source changed")
output_root = Path(os.environ.get("VERICLUE_DATA_OUTPUT", "/content/vericlue-dnu-bonafide"))
output_root.parent.mkdir(parents=True, exist_ok=True)
script = output_root.parent / ("prepare_nes2net_data-" + SOURCE_SHA256[:12] + ".py")
if script.exists() and script.read_text("utf-8") != source:
    raise ValueError("Existing embedded source differs")
if not script.exists():
    with script.open("x", encoding="utf-8", newline="\\n") as handle:
        handle.write(source)
job = runpy.run_path(str(script))
report = job["prepare"](output_root, per_speaker=20, seed=42, commit=SOURCE_COMMIT, workers=4)
print(json.dumps({{key: value for key, value in report.items() if key != "rows"}}, ensure_ascii=False))
if report["errors"]:
    raise ValueError("Preparation incomplete; keep evidence and rerun to resume, do not fit")
archive = output_root.parent / (output_root.name + "-" + __import__("uuid").uuid4().hex[:8] + ".zip")
archive_sha256 = job["archive_bundle"](output_root, archive)
print(json.dumps({{"archive": str(archive), "sha256": archive_sha256, "calibration_ready": False, "missing": ["attack_data"]}}))
"""
    markdown = """# VeriClue — chuẩn bị lớp giọng thật NES2Net

Chạy trên Colab/Kaggle CPU, không cần GPU, Drive mount hoặc token.
Chỉ tải dữ liệu publisher DNU đã ghim revision; giữ split theo người, kiểm SHA/
PCM và xuất bundle. Chưa có lớp tấn công, không fit/chọn ngưỡng hoặc sinh clone.
Giữ notebook private, không chia sẻ audio/output công khai.
Chỉ tải bundle sau khi cell chạy xong và kiểm hash; test vẫn dành đánh giá cuối.
"""
    download = """# Chỉ tải bundle đã kiểm; không cài artifact hay thay cấu hình API.
from google.colab import files
files.download(str(archive))
"""
    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": markdown.splitlines(keepends=True)},
        {
            "cell_type": "code",
            "metadata": {},
            "source": code.splitlines(keepends=True),
            "outputs": [],
            "execution_count": None,
        },
        {
            "cell_type": "code",
            "metadata": {},
            "source": download.splitlines(keepends=True),
            "outputs": [],
            "execution_count": None,
        },
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "vericlue": {"source_commit": commit, "source_dirty": dirty, "script_sha256": digest},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    source = SOURCE.read_text("utf-8")
    if args.check:
        if not args.output.is_file():
            return 1
        document = json.loads(args.output.read_text("utf-8"))
        expected = build(source, document["metadata"]["vericlue"]["source_commit"], dirty=False)
        return 0 if document == expected else 1
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, encoding="utf-8"
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--", str(SOURCE)], cwd=ROOT, encoding="utf-8"
        ).strip()
    )
    document = build(source, commit, dirty=dirty)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated {args.output.name}; source_dirty={dirty}; source_commit={commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
