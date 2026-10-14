"""Test cho scripts/plan_check.py — vừa test logic, vừa kiểm tra backlog thật của dự án."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("plan_check", ROOT / "scripts" / "plan_check.py")
pc = importlib.util.module_from_spec(spec)
sys.modules["plan_check"] = pc
spec.loader.exec_module(pc)


def make(tid, deps=(), sprint="S1", days=1.0, roles=("M1",), status="todo"):
    return pc.Task(
        id=tid,
        title=tid,
        roles=list(roles),
        owner="",
        days=days,
        sprints=pc.parse_sprints(sprint),
        priority="P0",
        deps=list(deps),
        status=status,
        starred=False,
        line=0,
    )


def test_parse_sprints_range():
    assert pc.parse_sprints("S1–S2") == ["S1", "S2"]
    assert pc.parse_sprints("S0") == ["S0"]
    assert pc.parse_sprints("DP (05/11)") == ["DP"]


def test_parse_roles_ignores_helpers():
    assert pc.parse_roles("M5 (+M1)") == ["M5"]
    assert pc.parse_roles("M3 + M4") == ["M3", "M4"]


def test_cycle_detected():
    tasks = {t.id: t for t in [make("AAA-01", ["AAA-02"]), make("AAA-02", ["AAA-01"])]}
    assert pc.find_cycles(tasks)


def test_critical_path_picks_longest_chain():
    tasks = {
        t.id: t
        for t in [
            make("AAA-01", days=1),
            make("AAA-02", ["AAA-01"], days=3),
            make("AAA-03", ["AAA-01"], days=1),
            make("AAA-04", ["AAA-02", "AAA-03"], days=1),
        ]
    }
    length, path = pc.critical_path(tasks)
    assert length == 5
    assert path == ["AAA-01", "AAA-02", "AAA-04"]


def test_load_splits_across_roles_and_sprints_and_skips_done():
    load = pc.load_table(
        [
            make("AAA-01", sprint="S1–S2", days=2, roles=("M1", "M2")),
            make("AAA-02", days=5, status="done"),
        ]
    )
    assert load["M1"]["S1"] == 0.5
    assert load["M2"]["S2"] == 0.5
    assert sum(sum(v.values()) for v in load.values()) == 2  # task done không tính


def test_compare_card_detects_mismatch():
    t = make("AAA-01", deps=["BBB-01"], sprint="S1", days=1)
    card = {"Người": "M2", "Ước lượng": "1", "Sprint": "S1", "Ưu tiên": "P0", "Phụ thuộc": "BBB-01"}
    diffs = pc.compare_card(t, card)
    assert len(diffs) == 1 and "vai trò" in diffs[0]


def test_real_backlog_is_valid(capsys):
    """Backlog thật của dự án phải qua kiểm tra (0 lỗi)."""
    assert pc.report(pc.parse_backlog(), util=0.7) == 0
    out = capsys.readouterr().out
    assert "0 lỗi" in out
