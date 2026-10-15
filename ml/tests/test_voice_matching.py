"""Text normalization and two-layer voice matching without model dependencies."""

from __future__ import annotations

import sys
import unicodedata
from types import ModuleType

import pytest

from vericlue_ml.voice.challenge import (
    MAX_SYLLABLE_WER,
    MIN_UNACCENTED_SIMILARITY,
    compare_transcripts,
    normalize_text,
    strip_diacritics,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  XIN—CHÀO,\n bạn!  ", "xin chào bạn"),
        ("xin_chào / bạn; tốt?", "xin chào bạn tốt"),
        ("", ""),
        ("...?!", ""),
        ("Tôi đọc 24 và 15.", "tôi đọc hai mươi tư và mười lăm"),
        ("105", "một trăm linh năm"),
        ("21", "hai mươi mốt"),
        ("0", "không"),
        ("007", "không không bảy"),
        ("-105", "âm một trăm linh năm"),
        ("12.5", "mười hai phẩy năm"),
        ("1000", "một nghìn"),
        ("1000000", "một triệu"),
        ("1000000000", "một tỷ"),
    ],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_normalization_composes_unicode_and_is_idempotent():
    raw = unicodedata.normalize("NFD", "HÒA bình, đọc 24 lần!")
    normalized = normalize_text(raw)
    assert unicodedata.is_normalized("NFC", normalized)
    assert normalized == normalize_text("Hoà bình, đọc hai mươi tư lần")
    assert normalize_text(normalized) == normalized


@pytest.mark.parametrize(("first", "second"), [("hòa", "hoà"), ("khỏe", "khoẻ"), ("thủy", "thuỷ")])
def test_equivalent_vietnamese_tone_positions_are_canonicalized(first, second):
    assert normalize_text(first) == normalize_text(second)


def test_strip_diacritics_preserves_words_and_maps_crossed_d():
    assert strip_diacritics("đường phố việt nam") == "duong pho viet nam"
    assert strip_diacritics(unicodedata.normalize("NFD", "đường phố")) == "duong pho"


@pytest.mark.parametrize("invalid", [None, 42, False, ["xin chào"]])
def test_normalization_rejects_non_string_values(invalid):
    with pytest.raises(TypeError):
        normalize_text(invalid)
    with pytest.raises(TypeError):
        strip_diacritics(invalid)


def edit_distance(first, second):
    previous = list(range(len(second) + 1))
    for index, item in enumerate(first, 1):
        current = [index]
        for other_index, other in enumerate(second, 1):
            current.append(
                min(
                    previous[other_index] + 1,
                    current[-1] + 1,
                    previous[other_index - 1] + (item != other),
                )
            )
        previous = current
    return previous[-1]


def lcs_length(first, second):
    previous = [0] * (len(second) + 1)
    for char in first:
        current = [0]
        for index, other in enumerate(second, 1):
            current.append(
                previous[index - 1] + 1 if char == other else max(previous[index], current[-1])
            )
        previous = current
    return previous[-1]


@pytest.fixture
def fake_match_libraries(monkeypatch):
    """Use independent tiny edit-distance/Indel oracles, not production helpers."""
    calls = []
    jiwer = ModuleType("jiwer")
    rapidfuzz = ModuleType("rapidfuzz")
    fuzz = ModuleType("rapidfuzz.fuzz")

    def wer(reference, hypothesis):
        calls.append(("wer", reference, hypothesis))
        return edit_distance(reference.split(), hypothesis.split()) / len(reference.split())

    def ratio(first, second):
        calls.append(("ratio", first, second))
        total = len(first) + len(second)
        return 200 * lcs_length(first, second) / total if total else 100.0

    jiwer.wer = wer
    fuzz.ratio = ratio
    rapidfuzz.fuzz = fuzz
    monkeypatch.setitem(sys.modules, "jiwer", jiwer)
    monkeypatch.setitem(sys.modules, "rapidfuzz", rapidfuzz)
    monkeypatch.setitem(sys.modules, "rapidfuzz.fuzz", fuzz)
    return jiwer, fuzz, calls


def test_matching_thresholds_are_the_task_values():
    assert MAX_SYLLABLE_WER == 0.3
    assert MIN_UNACCENTED_SIMILARITY == 0.9


def test_identical_normalized_text_passes_both_layers(fake_match_libraries):
    result = compare_transcripts("Tôi đọc 24 lần!", "tôi đọc hai mươi tư lần")
    assert result.matched is True
    assert result.syllable_wer == 0
    assert result.unaccented_similarity == 1
    assert result.expected_normalized == result.recognized_normalized == "tôi đọc hai mươi tư lần"


def test_completely_different_text_fails(fake_match_libraries):
    result = compare_transcripts(
        "con mèo đang ngủ bên cửa sổ nhà tôi", "hãy đọc số điện thoại của người bạn mới"
    )
    assert result.matched is False
    assert result.syllable_wer > MAX_SYLLABLE_WER
    assert result.unaccented_similarity < MIN_UNACCENTED_SIMILARITY


def test_correct_syllable_count_and_high_unaccented_similarity_still_require_tones(
    fake_match_libraries,
):
    result = compare_transcripts("má mà mả mã mạ ma", "ma ma ma ma ma ma")
    assert result.syllable_wer == pytest.approx(5 / 6)
    assert result.unaccented_similarity == 1
    assert result.matched is False


@pytest.mark.parametrize(
    ("wer", "ratio", "matched"),
    [(0.3, 90.0, True), (0.300001, 100.0, False), (0.0, 89.999, False), (0.31, 89.0, False)],
)
def test_threshold_boundaries_require_both_inclusive_conditions(
    fake_match_libraries, wer, ratio, matched
):
    jiwer, fuzz, _ = fake_match_libraries
    jiwer.wer = lambda reference, hypothesis: wer
    fuzz.ratio = lambda first, second: ratio
    result = compare_transcripts("câu tiếng việt", "câu tiếng việt")
    assert result.matched is matched
    assert result.syllable_wer == wer
    assert result.unaccented_similarity == pytest.approx(ratio / 100)


def test_wer_uses_accents_but_similarity_uses_unaccented_normalized_text(fake_match_libraries):
    _, _, calls = fake_match_libraries
    compare_transcripts("ĐƯỜNG, phố!", "đường phố")
    assert ("wer", "đường phố", "đường phố") in calls
    assert ("ratio", "duong pho", "duong pho") in calls


@pytest.mark.parametrize("recognized", ["", "  ", "...?!"])
def test_empty_recognized_text_fails_closed(fake_match_libraries, recognized):
    result = compare_transcripts("xin chào bạn", recognized)
    assert result.matched is False
    assert result.syllable_wer == 1
    assert result.unaccented_similarity == 0


@pytest.mark.parametrize("expected", ["", "   ", "...?!"])
def test_empty_expected_prompt_is_invalid(fake_match_libraries, expected):
    with pytest.raises(ValueError):
        compare_transcripts(expected, "xin chào bạn")


@pytest.mark.parametrize("invalid", [None, 42, False, ["xin chào"]])
def test_matcher_rejects_non_string_inputs(fake_match_libraries, invalid):
    with pytest.raises(TypeError):
        compare_transcripts(invalid, "xin chào bạn")
    with pytest.raises(TypeError):
        compare_transcripts("xin chào bạn", invalid)


def test_real_libraries_agree_with_independent_oracles_when_installed():
    pytest.importorskip("jiwer")
    pytest.importorskip("rapidfuzz")
    expected = "tôi đang đọc câu tiếng việt cho bạn nghe"
    recognized = "tôi đang đọc câu tiếng việt cho mẹ nghe"
    result = compare_transcripts(expected, recognized)
    assert result.syllable_wer == pytest.approx(1 / 9)
    first, second = strip_diacritics(expected), strip_diacritics(recognized)
    assert result.unaccented_similarity == pytest.approx(
        2 * lcs_length(first, second) / (len(first) + len(second))
    )


@pytest.mark.parametrize("word", ["quyển", "quyết", "tuyển", "chuyển", "nguyệt", "ngoại", "hoài"])
def test_canonical_tone_preserves_long_vowel_clusters(word):
    assert normalize_text(word) == word
