"""packages/contracts/openapi.json đã commit phải khớp code (sinh lại bằng scripts/gen_openapi.py)."""

from __future__ import annotations

import importlib.util

from contract_utils import ROOT

SCRIPT = ROOT / "scripts" / "gen_openapi.py"


def test_committed_openapi_matches_code():
    spec = importlib.util.spec_from_file_location("gen_openapi", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = module.OUT.read_text(encoding="utf-8")
    assert committed == module.render(), "chạy: uv run python scripts/gen_openapi.py"
