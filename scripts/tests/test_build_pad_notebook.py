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


@pytest.mark.parametrize("model", ["prep", "minifasnet", "dinov2"])
def test_committed_notebook_matches_repo_code(model):
    b = builder()
    on_disk = json.loads(b.NOTEBOOKS[model].read_text(encoding="utf-8"))
    fresh = b.build_notebook("TEST", False, model)
    assert [_strip_volatile(c) for c in _code_cells(on_disk)] == [
        _strip_volatile(c) for c in _code_cells(fresh)
    ], "Notebook lệch code repo: chạy `uv run python scripts/build_pad_notebook.py`."
    for cell in on_disk["cells"]:
        assert cell.get("outputs", []) == [], "Notebook phải được nbstripout (không có output)."


def test_embedded_code_is_self_contained():
    pytest.importorskip("sklearn")
    b = builder()
    cells = _code_cells(b.build_notebook("TEST", False, "minifasnet"))
    namespace: dict = {}
    exec(cells[1], namespace)  # nguồn + manifest
    for cell in cells[3:7]:  # pad.py, metrics.py, pad_tuning.py, calibration.py
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


def test_training_notebooks_differ_only_in_model_line_and_prep_is_separate():
    b = builder()
    mini = _code_cells(b.build_notebook("TEST", False, "minifasnet"))
    dino = _code_cells(b.build_notebook("TEST", False, "dinov2"))
    prep = _code_cells(b.build_notebook("TEST", False, "prep"))
    assert 'MODEL = "minifasnet"' in mini[2] and 'MODEL = "dinov2"' in dino[2]
    assert 'MODEL = "prep"' in prep[2]
    assert all("Thông tin môi trường" in nb[0] for nb in (mini, dino, prep))
    assert [c for c in mini if "MODEL = " not in c] == [c for c in dino if "MODEL = " not in c]
    # Notebook dạy KHÔNG tự chia tập; chỉ prep có bước làm sạch/chia và cổng lộ đề.
    assert not any("split_of = assign_splits(" in c for c in mini)
    assert any("split_of = assign_splits(" in c for c in prep) and any(
        "LEAK_AUC_MAX" in c for c in prep
    )
    assert any("KHÔNG TÌM THẤY DỮ LIỆU ĐÃ CHUẨN BỊ" in c for c in mini)
    assert not any("EXPECTED_SPLITS_SHA" in c for c in mini + prep)
    assert mini[3:7] == prep[3:7]  # cùng code nhúng
    assert not (b.ROOT / "ml" / "notebooks" / "finetune_pad.ipynb").exists()
    with pytest.raises(ValueError):
        b.build_notebook("TEST", False, "both")
