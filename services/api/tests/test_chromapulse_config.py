"""packages/contracts/chromapulse.json là nguồn duy nhất của bảng màu, nhịp và giới hạn (ADR-0011)."""

from __future__ import annotations

import json
import random

import pytest
from contract_utils import ROOT, defs

from vericlue_api.core import chromapulse_config
from vericlue_api.core.chromapulse_config import DEFAULT_PATH, load_chromapulse_config
from vericlue_api.core.config import Settings
from vericlue_api.services import challenge
from vericlue_api.services.challenge import generate_challenge, validate_palette

FILE = ROOT / "packages" / "contracts" / "chromapulse.json"


def test_api_reads_the_shared_contract_file():
    assert DEFAULT_PATH.resolve() == FILE.resolve()
    raw = json.loads(FILE.read_text(encoding="utf-8"))
    cfg = load_chromapulse_config()
    assert list(cfg.palette) == raw["palette"]
    assert Settings().palette == raw["palette"]  # mặc định lấy từ file, không cứng trong code


def test_challenge_module_uses_values_from_the_file():
    raw = json.loads(FILE.read_text(encoding="utf-8"))
    assert raw["steps"] == challenge.STEPS
    assert raw["baseline_ms"] == challenge.BASELINE_MS
    assert (raw["hold_ms"]["min"], raw["hold_ms"]["max"]) == challenge.HOLD_RANGE_MS
    assert raw["transition_ms"] == challenge.TRANSITION_MS
    assert raw["limits"]["max_luminance_spread"] == challenge.MAX_LUMINANCE_SPREAD
    assert raw["limits"]["max_red_share"] == challenge.MAX_RED_SHARE


def test_file_keeps_adr_0011_safety_limits():
    """File có thể đổi bảng màu, nhưng không được nới các giới hạn an toàn của ADR-0011."""
    cfg = load_chromapulse_config()
    assert cfg.steps == 8
    assert cfg.max_changes_per_second <= 2.5
    assert cfg.max_luminance_spread <= 0.064
    assert cfg.max_red_share <= 0.8
    validate_palette(list(cfg.palette))
    shortest_step_ms = cfg.hold_min_ms + cfg.transition_ms
    assert 1000 / shortest_step_ms <= cfg.max_changes_per_second
    assert shortest_step_ms >= 550


def test_hold_and_transition_match_the_session_schema():
    step = defs("session")["ColorStep"]["properties"]
    cfg = load_chromapulse_config()
    assert step["hold_ms"]["minimum"] == cfg.hold_min_ms
    assert step["hold_ms"]["maximum"] == cfg.hold_max_ms
    assert step["transition_ms"]["const"] == cfg.transition_ms


def test_generated_challenge_follows_the_file():
    cfg = load_chromapulse_config()
    ch = generate_challenge(Settings(), rng=random.Random(7))
    assert len(ch.color_sequence) == cfg.steps
    assert ch.baseline_ms == cfg.baseline_ms
    assert {s.rgb for s in ch.color_sequence} <= set(cfg.palette)


def test_config_path_can_be_overridden(tmp_path, monkeypatch):
    raw = json.loads(FILE.read_text(encoding="utf-8"))
    raw["palette"] = ["#ffcc73", "#80e09e"]
    other = tmp_path / "chromapulse.json"
    other.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("CHROMAPULSE_CONFIG", str(other))
    chromapulse_config.load_chromapulse_config.cache_clear()
    try:
        assert Settings().palette == ["#ffcc73", "#80e09e"]
    finally:
        monkeypatch.delenv("CHROMAPULSE_CONFIG")
        chromapulse_config.load_chromapulse_config.cache_clear()


@pytest.mark.parametrize(
    "key", ["palette", "baseline_color", "steps", "hold_ms", "transition_ms", "limits"]
)
def test_file_has_required_keys(key):
    assert key in json.loads(FILE.read_text(encoding="utf-8"))


def test_missing_config_file_gives_clear_error_with_tried_path(tmp_path, monkeypatch):
    missing = tmp_path / "nope" / "chromapulse.json"
    monkeypatch.setenv("CHROMAPULSE_CONFIG", str(missing))
    chromapulse_config.load_chromapulse_config.cache_clear()
    try:
        with pytest.raises(FileNotFoundError) as info:
            load_chromapulse_config()
        message = str(info.value)
        assert str(missing) in message  # nói rõ đường dẫn đã thử
        assert "CHROMAPULSE_CONFIG" in message  # và cách khắc phục
    finally:
        monkeypatch.delenv("CHROMAPULSE_CONFIG")
        chromapulse_config.load_chromapulse_config.cache_clear()
