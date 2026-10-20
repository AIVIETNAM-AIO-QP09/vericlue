"""Sinh notebook hiệu chỉnh GenD cho Kaggle/Colab từ khuôn `ml/notebooks/templates/*.py` (FACE-04).

Repo là private nên notebook KHÔNG clone repo: code cần thiết (tiền xử lý GenD thật trong
`ml/src/vericlue_ml/face/`, hàm thuần `finetune/`, `models/manifest.yaml`, `nb_common.py`) được NHÚNG
nguyên văn vào ô `# %% [embed]`, kèm commit nguồn và SHA-256 từng file. Khi chạy, notebook ghi các file
ra đĩa, kiểm SHA-256 rồi thêm vào `sys.path`.

    uv run python scripts/build_gend_notebooks.py          # sinh lại notebook
    uv run python scripts/build_gend_notebooks.py --check  # chỉ kiểm notebook có khớp code hiện tại không

Sửa logic thì sửa khuôn hoặc file nguồn rồi chạy lại script; KHÔNG sửa tay file .ipynb.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "ml" / "notebooks" / "templates"
OUT_DIR = ROOT / "ml" / "notebooks"
SRC = ROOT / "ml" / "src"

# (đường dẫn trong repo, đường dẫn khi ghi ra trong notebook)
_PACKAGE = [
    "vericlue_ml/__init__.py",
    "vericlue_ml/common/__init__.py",
    "vericlue_ml/common/result.py",
    "vericlue_ml/common/detector.py",
    "vericlue_ml/common/device.py",
    "vericlue_ml/common/calibration.py",
    "vericlue_ml/face/__init__.py",
    "vericlue_ml/face/pad.py",
    "vericlue_ml/face/frames.py",
    "vericlue_ml/face/gend.py",
    "vericlue_ml/eval/__init__.py",
    "vericlue_ml/eval/metrics.py",
    "vericlue_ml/finetune/__init__.py",
    "vericlue_ml/finetune/data04.py",
    "vericlue_ml/finetune/gend_train.py",
    "vericlue_ml/finetune/gend_calib.py",
]
EMBED: list[tuple[str, str]] = [
    *((f"ml/src/{p}", p) for p in _PACKAGE),
    ("models/manifest.yaml", "models/manifest.yaml"),
    ("ml/notebooks/templates/nb_common.py", "nb_common.py"),
]
NOTEBOOKS = {
    "calibrate_gend": "FACE-04 — Hiệu chỉnh điểm GenD (calibration, không dạy lại)",
}


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def source_files() -> dict[str, tuple[str, str]]:
    """{đường dẫn ghi ra: (sha256, nội dung)} — đọc nguyên văn, chuẩn hóa xuống dòng LF."""
    out: dict[str, tuple[str, str]] = {}
    for repo_path, target in EMBED:
        text = (ROOT / repo_path).read_text(encoding="utf-8").replace("\r\n", "\n")
        out[target] = (hashlib.sha256(text.encode("utf-8")).hexdigest(), text)
    return out


def embed_cell(files: dict[str, tuple[str, str]]) -> str:
    commit = _git("rev-parse", "HEAD") or "unknown"
    dirty = bool(_git("status", "--porcelain", "--", *(p for p, _ in EMBED)))
    lines = [
        "# ===================== CODE NHÚNG TỪ REPO (KHÔNG SỬA TAY) =====================",
        "# Sinh bởi scripts/build_gend_notebooks.py. Tiền xử lý GenD lấy NGUYÊN VĂN từ",
        "# ml/src/vericlue_ml/face/{gend,pad,frames}.py để giống hệt hệ thống đang chạy.",
        f'SOURCE_COMMIT = "{commit}"',
        f"SOURCE_DIRTY = {dirty}  # True = lúc sinh notebook có file nhúng chưa commit",
        "import hashlib as _hashlib",
        "import os as _os",
        "import sys as _sys",
        "from pathlib import Path as _Path",
        "",
        "_EMBEDDED = {",
    ]
    for target, (digest, text) in sorted(files.items()):
        lines.append(f"    {target!r}: ({digest!r}, {text!r}),")
    lines += [
        "}",
        '_SRC = _Path(_os.environ.get("VC_SRC", "vc_src")).resolve()',
        "for _name, (_digest, _text) in _EMBEDDED.items():",
        '    if _hashlib.sha256(_text.encode("utf-8")).hexdigest() != _digest:',
        '        raise RuntimeError(f"Code nhúng bị sửa: {_name}")',
        "    _path = _SRC / _name",
        "    _path.parent.mkdir(parents=True, exist_ok=True)",
        '    _path.write_text(_text, encoding="utf-8")',
        "if str(_SRC) not in _sys.path:",
        "    _sys.path.insert(0, str(_SRC))",
        '_os.environ["ML_MODELS_MANIFEST"] = str(_SRC / "models" / "manifest.yaml")',
        'print(f"Code nhúng: {len(_EMBEDDED)} file từ commit {SOURCE_COMMIT[:12]}'
        "{' (có sửa chưa commit)' if SOURCE_DIRTY else ''} → {_SRC}\")",
    ]
    return "\n".join(lines)


def parse_template(text: str) -> list[tuple[str, str]]:
    """Khuôn dạng percent (`# %%`, `# %% [markdown]`, `# %% [embed]`) → [(loại, nội dung)]."""
    cells: list[tuple[str, list[str]]] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("# %%"):
            tag = line[4:].strip()
            kind = {"[markdown]": "markdown", "[embed]": "embed"}.get(tag, "code")
            cells.append((kind, []))
            continue
        if not cells:
            continue
        cells[-1][1].append(line)
    out = []
    for kind, body in cells:
        if kind == "markdown":
            body = [b[2:] if b.startswith("# ") else b.lstrip("#") for b in body]
        content = "\n".join(body).strip("\n")
        out.append((kind, content))
    return out


def _source_lines(text: str) -> list[str]:
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def build_notebook(name: str, files: dict[str, tuple[str, str]]) -> dict:
    cells = []
    for index, (kind, content) in enumerate(
        parse_template((TEMPLATES / f"{name}.py").read_text("utf-8"))
    ):
        if kind == "embed":
            kind, content = "code", embed_cell(files)
        cell = {
            "cell_type": kind,
            "id": str(index),  # giống nbstripout để hook pre-commit không sửa file
            "metadata": {},
            "source": _source_lines(content),
        }
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "kaggle": {"accelerator": "gpu", "isGpuEnabled": True, "isInternetEnabled": True},
            "vericlue": {"title": NOTEBOOKS[name], "generator": "scripts/build_gend_notebooks.py"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def embedded_hashes(notebook: dict) -> dict[str, str]:
    """Đọc lại {file: sha256} trong ô nhúng của một notebook đã sinh (dùng cho --check và test)."""
    import ast

    for cell in notebook["cells"]:
        text = "".join(cell["source"])
        if "_EMBEDDED = {" in text:
            start = text.index("_EMBEDDED = {") + len("_EMBEDDED = ")
            end = text.index("\n}\n", start) + 2
            return {k: v[0] for k, v in ast.literal_eval(text[start:end]).items()}
    return {}


def render(notebook: dict) -> str:
    """JSON giống hệt đầu ra của nbstripout (khóa sắp xếp, thụt 1) để hook không sửa lại file."""
    return json.dumps(notebook, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _without_commit(text: str) -> str:
    """Bỏ dòng commit/dirty (đổi theo mỗi commit) khi so notebook với khuôn."""
    return "\n".join(
        line
        for line in text.replace("\r\n", "\n").split("\n")
        if "SOURCE_COMMIT = " not in line and "SOURCE_DIRTY = " not in line
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="chỉ kiểm, không ghi")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    files = source_files()
    want = {k: v[0] for k, v in files.items()}
    stale = []
    for name in NOTEBOOKS:
        path = OUT_DIR / f"{name}.ipynb"
        if not (TEMPLATES / f"{name}.py").exists():
            continue
        text = render(build_notebook(name, files))
        if args.check:
            current = path.read_text("utf-8") if path.exists() else ""
            if embedded_hashes(json.loads(current or "{}")) != want or _without_commit(
                current
            ) != _without_commit(text):
                stale.append(path.name)
            continue
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"Đã sinh {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
    if stale:
        print("Notebook lệch code (chạy lại scripts/build_gend_notebooks.py):", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
