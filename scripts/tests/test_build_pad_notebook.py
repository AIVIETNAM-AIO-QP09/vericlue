"""FACE-04 — notebook tinh chỉnh PAD phải khớp code sản phẩm đang nhúng."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def builder():
    return importlib.import_module("build_pad_notebook")


def _code_cells(nb: dict) -> list[str]:
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def _strip_volatile(text: str) -> str:
    keep = []
    for line in text.splitlines():
        if line.startswith(("SOURCE_COMMIT = ", "SOURCE_DIRTY = ", "# === NHÚNG TỪ ")):
            continue
        keep.append(line)
    return "\n".join(keep)


def test_committed_notebook_matches_repo_code():
    b = builder()
    on_disk = json.loads(b.NOTEBOOK.read_text(encoding="utf-8"))
    fresh = b.build_notebook("TEST", False)
    assert [_strip_volatile(c) for c in _code_cells(on_disk)] == [
        _strip_volatile(c) for c in _code_cells(fresh)
    ], "Notebook lệch code repo: chạy `uv run python scripts/build_pad_notebook.py`."
    for cell in on_disk["cells"]:
        assert cell.get("outputs", []) == [], "Notebook phải được nbstripout (không có output)."


def test_embedded_code_is_self_contained():
    pytest.importorskip("sklearn")
    b = builder()
    cells = _code_cells(b.build_notebook("TEST", False))
    namespace: dict = {}
    exec(cells[0], namespace)  # nguồn + manifest
    for cell in cells[2:5]:  # pad.py, metrics.py, pad_tuning.py
        exec(compile(cell, "<notebook>", "exec"), namespace)
    for name in ("ScrfdFaceFinder", "MiniFasNetClassifier", "auc", "eer", "apcer_by_attack",
                 "assign_splits", "assert_not_test", "leak_auc", "pad_crop"):  # fmt: skip
        assert name in namespace
    assert set(namespace["MANIFEST"]) == set(b.MODEL_IDS)
    for entry in namespace["MANIFEST"].values():
        assert entry["revision"] and all(len(f["sha256"]) == 64 for f in entry["files"])


def test_extract_fails_loudly_when_name_disappears():
    b = builder()
    with pytest.raises(SystemExit):
        b.extract(b.PAD_PY, ("NoSuchThing",))
