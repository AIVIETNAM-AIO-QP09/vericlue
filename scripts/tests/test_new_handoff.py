"""Test cho scripts/new_handoff.py."""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("new_handoff", ROOT / "scripts" / "new_handoff.py")
nh = importlib.util.module_from_spec(spec)
sys.modules["new_handoff"] = nh
spec.loader.exec_module(nh)


def test_slug():
    assert nh.slug("Quoc + Claude") == "quoc-claude"
    assert nh.slug("FACE-02") == "face-02"


def test_create_uses_template(tmp_path, monkeypatch):
    monkeypatch.setattr(nh, "HANDOFFS", tmp_path)
    path = nh.create("face-02", "Quoc+Codex", now=datetime(2026, 10, 20, 9, 30))
    assert path.name == "2026-10-20-0930-face-02-quoc-codex.md"
    text = path.read_text(encoding="utf-8")
    assert "FACE-02" in text and "Quoc+Codex" in text and "{{" not in text
