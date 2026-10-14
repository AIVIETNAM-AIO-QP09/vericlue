"""TẠM — ROUT-02 thay thế bằng TrustRouter đầy đủ (ngưỡng khóa trong ml/configs/thresholds.yaml).

Luật quyết định tạm cho `finalize` và `voice`, thứ tự cổng:
  phiên hợp lệ (router) → quality → chromapulse/camprobe → ngưỡng B/A trên khuôn mặt → voice.
`error`/`degraded` ở bước bắt buộc → `review`, không bao giờ `pass` (AGENTS.md §6 luật 4).
Hàm thuần: không đọc cấu hình, không I/O; test theo bảng kịch bản mock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vericlue_ml.common.result import Gate, Module, ModuleResult, Status

Status4 = Literal["pass", "retry", "review", "voice_challenge"]
Priority = Literal["normal", "high"]

FACE_MODULES = (Module.FACE_PAD, Module.FACE_DEEPFAKE)
PRESENCE_MODULES = (Module.CHROMAPULSE, Module.CAMPROBE)
VOICE_MODULES = (Module.VOICE_SPOOF, Module.LIPSYNC)
FINALIZE_MODULES = (Module.QUALITY, *FACE_MODULES, *PRESENCE_MODULES)
VOICE_STEP_MODULES = (Module.VOICE_CHALLENGE, *VOICE_MODULES)

MAX_VOICE_REREADS = 1
DEFAULT_RETRY_HINT = "MORE_LIGHT"
PRESENCE_RETRY_HINT = "BRIGHTNESS_UP"


@dataclass(frozen=True)
class Outcome:
    status: Status4
    retry_hint: str | None = None
    priority: Priority = "normal"
    reason: str = ""  # chỉ để ghi log/bằng chứng nội bộ, không trả cho người dân


def _ok(r: ModuleResult | None) -> bool:
    return r is not None and r.status == Status.OK


def _evidence_value(r: ModuleResult, name: str) -> str | None:
    for e in r.evidence:
        if e.name == name and isinstance(e.value, str):
            return e.value
    return None


def fused_prob(results: dict[Module, ModuleResult], modules: tuple[Module, ...]) -> float | None:
    """Max `prob_attack` của các module có `status = ok`; None nếu không module nào dùng được."""
    probs = [
        r.prob_attack for m in modules if _ok(r := results.get(m)) and r.prob_attack is not None
    ]
    return max(probs) if probs else None


def _retry_or_review(retries_used: int, max_retries: int, hint: str, reason: str) -> Outcome:
    if retries_used >= max_retries:
        return Outcome("review", reason=f"{reason}; quá {max_retries} lần chụp lại")
    return Outcome("retry", retry_hint=hint, reason=reason)


def decide_finalize(
    results: dict[Module, ModuleResult],
    *,
    retries_used: int,
    max_retries: int,
    b: float,
    a: float,
) -> Outcome:
    # 1. Chất lượng
    quality = results.get(Module.QUALITY)
    if not _ok(quality):
        return Outcome("review", reason="quality lỗi hoặc suy giảm")
    assert quality is not None
    if quality.gate != Gate.PASS:
        hint = _evidence_value(quality, "retry_hint") or DEFAULT_RETRY_HINT
        return _retry_or_review(retries_used, max_retries, hint, "quality không đạt")

    # 2. Hiện diện: lỗi → review; fail → review ưu tiên cao; chưa rõ → chụp lại
    presence = [results.get(m) for m in PRESENCE_MODULES]
    if not all(_ok(r) for r in presence):
        return Outcome("review", reason="chromapulse/camprobe lỗi hoặc suy giảm")
    gates = [r.gate for r in presence if r is not None]
    if Gate.FAIL in gates:
        return Outcome("review", priority="high", reason="hiện diện không đạt")
    if any(g != Gate.PASS for g in gates):
        return _retry_or_review(retries_used, max_retries, PRESENCE_RETRY_HINT, "hiện diện chưa rõ")

    # 3. Khuôn mặt: thiếu hoặc lỗi bất kỳ module nào → không bao giờ pass
    if not all(_ok(results.get(m)) for m in FACE_MODULES):
        return Outcome("review", reason="module khuôn mặt lỗi hoặc suy giảm")
    p = fused_prob(results, FACE_MODULES)
    if p is None:
        return Outcome("review", reason="thiếu xác suất khuôn mặt")
    if p < b:
        return Outcome("pass", reason=f"p={p:.2f} < B")
    if p < a:
        return Outcome("voice_challenge", reason=f"B <= p={p:.2f} < A")
    return Outcome("review", reason=f"p={p:.2f} >= A")


def decide_voice(results: dict[Module, ModuleResult], *, rereads_used: int, b: float) -> Outcome:
    if not all(_ok(results.get(m)) for m in (Module.VOICE_CHALLENGE, *VOICE_MODULES)):
        return Outcome("review", reason="module giọng nói lỗi hoặc suy giảm")
    challenge = results[Module.VOICE_CHALLENGE]
    if challenge.gate != Gate.PASS:
        if rereads_used < MAX_VOICE_REREADS:
            return Outcome("voice_challenge", reason="đọc sai câu")
        return Outcome("review", reason="đọc sai câu quá số lần cho phép")
    p = fused_prob(results, VOICE_MODULES)
    if p is None:
        return Outcome("review", reason="thiếu xác suất giọng nói")
    return Outcome("review" if p >= b else "pass", reason=f"p_voice={p:.2f}")
