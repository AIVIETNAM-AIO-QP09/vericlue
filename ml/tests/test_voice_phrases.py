"""Kiểm tra ngân hàng câu tự soạn, không cần mô hình hoặc âm thanh thật."""

from __future__ import annotations

import random
import unicodedata

import pytest

from vericlue_ml.voice import phrases
from vericlue_ml.voice.phrases import PROMPTS, generate_prompt

TONE_MARKS = {
    "\u0300": "huyen",
    "\u0301": "sac",
    "\u0309": "hoi",
    "\u0303": "nga",
    "\u0323": "nang",
}
ALL_TONES = {"ngang", *TONE_MARKS.values()}


def tone_of(syllable: str) -> str:
    tones = {
        TONE_MARKS[mark] for mark in unicodedata.normalize("NFD", syllable) if mark in TONE_MARKS
    }
    assert len(tones) <= 1, f"Âm tiết có nhiều dấu thanh: {syllable}"
    return next(iter(tones), "ngang")


def strip_marks(syllable: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", syllable.casefold())
        if not unicodedata.combining(char)
    ).replace("đ", "d")


@pytest.mark.parametrize("prompt", PROMPTS)
def test_every_prompt_has_eight_to_twelve_syllables_and_all_six_tones(prompt):
    syllables = prompt.split()
    assert 8 <= len(syllables) <= 12
    assert {tone_of(syllable) for syllable in syllables} == ALL_TONES
    assert unicodedata.normalize("NFC", prompt) == prompt
    assert not any(character.isdigit() for character in prompt)
    assert all(syllable.isalpha() for syllable in syllables)
    # Sentence-initial capitals are allowed; names are excluded by authored vocabulary.
    assert all(syllable == syllable.lower() for syllable in syllables[1:])


def test_bank_is_large_and_unique():
    assert isinstance(PROMPTS, tuple)
    assert len(PROMPTS) >= 20
    assert len(set(PROMPTS)) == len(PROMPTS)


def test_bank_covers_regional_consonant_pairs():
    syllables = {strip_marks(word) for prompt in PROMPTS for word in prompt.split()}
    for onset in ("tr", "ch", "s", "x", "r", "d", "gi"):
        assert any(word.startswith(onset) for word in syllables), onset
    assert any(word.endswith("n") for word in syllables)
    assert any(word.endswith("ng") for word in syllables)


@pytest.mark.parametrize("word", ["hai", "mười", "mươi", "lăm"])
def test_numbers_are_spelled_out_in_authored_prompts(word):
    assert any(word in prompt.split() for prompt in PROMPTS)


def test_first_prompt_remains_stable_for_fixed_tts_fixtures():
    assert PROMPTS[0] == "Buổi sáng mẹ vẫn mở cửa nhà cho em"


@pytest.mark.parametrize("previous", PROMPTS)
def test_new_prompt_never_repeats_previous(previous):
    for seed in range(10):
        result = generate_prompt(previous, rng=random.Random(seed))
        assert result in PROMPTS
        assert result != previous


def test_injected_rng_reproduces_sequence():
    first, second = random.Random(42), random.Random(42)
    assert [generate_prompt(rng=first) for _ in range(20)] == [
        generate_prompt(rng=second) for _ in range(20)
    ]


def test_default_selection_uses_system_random_and_excludes_previous(monkeypatch):
    calls = []

    def choose(candidates):
        calls.append(candidates)
        return candidates[-1]

    monkeypatch.setattr(phrases.secrets, "choice", choose)
    result = generate_prompt(PROMPTS[0])
    assert calls == [PROMPTS[1:]]
    assert result == PROMPTS[-1]


def test_unknown_previous_still_selects_from_bank():
    assert generate_prompt("Câu ngoài ngân hàng", rng=random.Random(7)) in PROMPTS
