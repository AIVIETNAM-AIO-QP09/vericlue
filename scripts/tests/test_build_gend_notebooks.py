"""Notebook hiệu chỉnh GenD phải khớp code repo (sinh lại bằng scripts/build_gend_notebooks.py)."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "build_gend_notebooks", ROOT / "scripts" / "build_gend_notebooks.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_notebook_in_sync_with_repo_code():
    assert builder.main(["--check"]) == 0


def test_notebook_embeds_real_gend_code_and_no_fake_generation():
    path = ROOT / "ml" / "notebooks" / "calibrate_gend.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    hashes = builder.embedded_hashes(notebook)
    assert {"vericlue_ml/face/gend.py", "vericlue_ml/finetune/gend_calib.py"} <= set(hashes)
    assert all(not c.get("outputs") for c in notebook["cells"] if c["cell_type"] == "code")
    # Ô nhúng chứa models/manifest.yaml (có SyncNet của LatentSync dùng để PHÁT HIỆN); chỉ xét ô viết tay.
    own = ["".join(c["source"]) for c in notebook["cells"]]
    own = [s for s in own if "_EMBEDDED = {" not in s]
    text = "\n".join(own).lower()
    for banned in ("facefusion", "musetalk", "latentsync", "inswapper_128.onnx", "lip-sync"):
        assert banned not in text
    assert "RUN_TEST = False" in "\n".join(own)
