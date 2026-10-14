"""Bộ sinh thử thách màu: 4 ràng buộc của ADR-0011 (§5) và nhịp an toàn."""

from __future__ import annotations

import random

import pytest
from contract_utils import validate

from vericlue_api.core.config import Settings
from vericlue_api.services.challenge import (
    generate_challenge,
    red_share,
    relative_luminance,
)

SEEDS = range(200)


def _make(seed: int, **overrides):
    return generate_challenge(Settings(**overrides), rng=random.Random(seed))


@pytest.mark.parametrize("seed", SEEDS)
def test_eight_colors_and_adjacent_differ(seed):
    seq = _make(seed).color_sequence
    assert len(seq) == 8
    assert all(a.rgb != b.rgb for a, b in zip(seq, seq[1:], strict=False))


@pytest.mark.parametrize("seed", SEEDS)
def test_at_most_2_5_changes_per_second(seed):
    for step in _make(seed).color_sequence:
        assert 1000 / (step.hold_ms + step.transition_ms) <= 2.5
        assert step.hold_ms + step.transition_ms >= 550  # tức <= 1,8 lần/giây
        assert 400 <= step.hold_ms <= 650 and step.transition_ms == 150


def test_default_palette_luminance_and_red_share():
    palette = Settings().palette
    lum = [relative_luminance(c) for c in palette]
    assert max(lum) - min(lum) <= 0.064
    assert all(red_share(c) < 0.8 for c in palette)


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_sequence_meets_luminance_and_red_limits(seed):
    colors = [s.rgb for s in _make(seed).color_sequence]
    lum = [relative_luminance(c) for c in colors]
    assert max(lum) - min(lum) <= 0.064
    assert all(red_share(c) < 0.8 for c in colors)


def test_challenge_matches_contract_and_expires_in_120_seconds():
    settings = Settings()
    ch = generate_challenge(settings)
    validate(ch.model_dump(mode="json", exclude_none=True), "session", "Challenge")
    assert settings.challenge_ttl_seconds == 120
    assert ch.expires_at is not None
    assert len(ch.capture_at_ms) == 2 and ch.capture_at_ms == sorted(ch.capture_at_ms)


def test_challenges_are_random_and_unique():
    ids = {generate_challenge(Settings()).challenge_id for _ in range(20)}
    assert len(ids) == 20
    seqs = {tuple(s.rgb for s in generate_challenge(Settings()).color_sequence) for _ in range(20)}
    assert len(seqs) > 1


def test_palette_is_configurable_not_hard_coded():
    ch = _make(1, challenge_palette="#ffcc73,#80e09e")
    assert {s.rgb for s in ch.color_sequence} <= {"#ffcc73", "#80e09e"}
    with pytest.raises(ValueError):
        _make(1, challenge_palette="#ffcc73")
