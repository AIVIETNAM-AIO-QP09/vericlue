"""Vietnamese phrase matching: VOICE-04, proposal section 2.7(d), ADR-0005."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.router.config import VoiceConfig, load_config

if TYPE_CHECKING:
    from vericlue_ml.voice.asr import PhoWhisperASR


def __getattr__(name: str) -> float:
    # Legacy imports remain supported without reading YAML while importing the module.
    if name == "MAX_SYLLABLE_WER":
        return load_config().voice.max_syllable_wer
    if name == "MIN_UNACCENTED_SIMILARITY":
        return load_config().voice.min_unaccented_similarity
    raise AttributeError(name)


_DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
_TONES = "\u0300\u0301\u0303\u0309\u0323"


def _integer_words(number: int) -> str:
    if number < 10:
        return _DIGITS[number]
    if number < 100:
        tens, last = divmod(number, 10)
        prefix = "mười" if tens == 1 else _DIGITS[tens] + " mươi"
        suffix = (
            "mốt"
            if last == 1 and tens > 1
            else "tư"
            if last == 4 and tens > 1
            else "lăm"
            if last == 5
            else _DIGITS[last]
        )
        return prefix + (" " + suffix if last else "")
    if number < 1000:
        hundreds, tail = divmod(number, 100)
        return (
            _DIGITS[hundreds]
            + " trăm"
            + (
                (" linh " + _DIGITS[tail] if tail < 10 else " " + _integer_words(tail))
                if tail
                else ""
            )
        )
    for scale, name in ((10**9, "tỷ"), (10**6, "triệu"), (1000, "nghìn")):
        if number >= scale:
            high, tail = divmod(number, scale)
            suffix = _integer_words(tail) if tail else ""
            if 0 < tail < 100:
                suffix = "không trăm " + ("linh " if tail < 10 else "") + suffix
            return _integer_words(high) + " " + name + (" " + suffix if tail else "")
    raise ValueError("Số không hợp lệ.")


def _number_words(match: re.Match) -> str:
    token = match.group()
    negative = token.startswith("-")
    token = token.lstrip("-")
    parts = re.split(r"[.,]", token)
    whole = parts[0]
    # Avoid guessing dates/phone numbers or losing leading zeros.
    result = (
        " ".join(_DIGITS[int(c)] for c in whole)
        if (len(whole) > 1 and whole.startswith("0")) or len(whole) > 12
        else _integer_words(int(whole))
    )
    if len(parts) == 2:
        result += " phẩy " + " ".join(_DIGITS[int(c)] for c in parts[1])
    return ("âm " if negative else "") + result


def _canonical_tone(token: str) -> str:
    # VOICE-04: preserve canonical Unicode text.
    decomposed = unicodedata.normalize("NFD", token)
    tones = [c for c in decomposed if c in _TONES]
    if len(tones) != 1:
        return token
    plain_tone = unicodedata.normalize("NFC", "".join(c for c in decomposed if c not in _TONES))
    cluster = next(
        (m for m in re.finditer(r"[aăâeêioôơuưy]+", plain_tone) if m.group() in {"oa", "oe", "uy"}),
        None,
    )
    if cluster:
        position = cluster.start() + 1
        plain_tone = plain_tone[: position + 1] + tones[0] + plain_tone[position + 1 :]
        return unicodedata.normalize("NFC", plain_tone)
    return token


def normalize_text(text: str) -> str:
    """Vietnamese challenge matching; VOICE-04 / proposal section 2.7(d)."""
    if not isinstance(text, str):
        raise TypeError("Văn bản phải là chuỗi.")
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"-?[0-9]+(?:[.,][0-9]+)?", _number_words, text)
    text = "".join(c if c.isalpha() or c.isspace() else " " for c in text)
    return " ".join(_canonical_tone(token) for token in text.split())


def strip_diacritics(text: str) -> str:
    """Vietnamese challenge matching; VOICE-04 / proposal section 2.7(d)."""
    return (
        "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
        .replace("đ", "d")
        .replace("Đ", "D")
    )


class MatchResult(BaseModel):
    """Vietnamese challenge matching; VOICE-04 / proposal section 2.7(d)."""

    model_config = ConfigDict(frozen=True)
    expected_normalized: str
    recognized_normalized: str
    syllable_wer: float
    unaccented_similarity: float
    matched: bool


def compare_transcripts(
    expected: str, recognized: str, *, config: VoiceConfig | None = None
) -> MatchResult:
    """Vietnamese challenge matching; VOICE-04 / proposal section 2.7(d)."""
    config = config if config is not None else load_config().voice
    reference, hypothesis = normalize_text(expected), normalize_text(recognized)
    if not reference:
        raise ValueError("Câu đề bài không được rỗng.")
    if not hypothesis:
        error, similarity = 1.0, 0.0
    else:
        from jiwer import wer
        from rapidfuzz.fuzz import ratio

        error = float(wer(reference, hypothesis))
        similarity = float(ratio(strip_diacritics(reference), strip_diacritics(hypothesis))) / 100
    return MatchResult(
        expected_normalized=reference,
        recognized_normalized=hypothesis,
        syllable_wer=error,
        unaccented_similarity=similarity,
        matched=error <= config.max_syllable_wer and similarity >= config.min_unaccented_similarity,
    )


class VoiceChallengeDetector:
    """Vietnamese challenge matching; VOICE-04 / proposal section 2.7(d)."""

    name = "voice_challenge"

    def __init__(self, asr: PhoWhisperASR | None = None) -> None:
        from vericlue_ml.voice.asr import PhoWhisperASR

        self.asr = asr if asr is not None else PhoWhisperASR()
        self.version = self.asr.version
        self.match_config: VoiceConfig | None = None

    def preload(self, *, models_dir: Path | None = None, device: str | None = None) -> None:
        """Prepare the ASR model without transcribing or supplying a prompt."""
        options = {}
        if models_dir is not None:
            options["models_dir"] = models_dir
        if device is not None:
            options["device"] = device
        self.asr.preload(**options)

    def predict(self, inp: DetectorInput) -> ModuleResult:
        """Return a content gate; infrastructure/decode failures never pass."""
        import time

        from vericlue_ml.common.result import ErrorCode, Evidence, ModuleResult
        from vericlue_ml.voice.asr import ASRError, DecodeError, SpeechNotFound

        started = time.perf_counter()
        base = dict(module=self.name, model_version=self.version)
        try:
            prompt = inp.metadata.get("prompt")
            if not isinstance(prompt, str) or not normalize_text(prompt):
                raise ValueError("Thiếu câu đề bài phía server.")
            if inp.audio is None:
                raise DecodeError("Thiếu audio.")
            transcript = self.asr.transcribe(
                inp.audio, expected_syllable_count=len(normalize_text(prompt).split())
            )
            match = compare_transcripts(prompt, transcript, config=self.match_config)
            return ModuleResult(
                **base,
                status="ok",
                gate="pass" if match.matched else "fail",
                error_code=None if match.matched else ErrorCode.E_CHALLENGE_MISMATCH,
                # ROUT-02: reading error rate, NOT an attack probability.
                score=match.syllable_wer,
                quality={
                    "syllable_error_rate": match.syllable_wer,
                    "unaccented_similarity": match.unaccented_similarity,
                },
                evidence=[
                    Evidence(type="text", name="recognized_text", value=transcript),
                    Evidence(type="text", name="expected_text", value=prompt),
                ],
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        except SpeechNotFound:
            status, code = "not_applicable", ErrorCode.E_LOW_QUALITY
        except DecodeError:
            status, code = "error", ErrorCode.E_DECODE
        except (ASRError, ImportError, OSError, ValueError, RuntimeError):
            status, code = "error", ErrorCode.E_INTERNAL
        except Exception:  # Provider failures must not escape as accepted decisions.
            status, code = "error", ErrorCode.E_INTERNAL
        return ModuleResult(
            **base,
            status=status,
            gate="unclear",
            error_code=code,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
