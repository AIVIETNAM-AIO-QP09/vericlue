"""Server-issued capture plan (LIVE-01); scoring belongs to the detector modules."""

from __future__ import annotations

import random
import secrets

from vericlue_api.core.config import Settings
from vericlue_api.schemas.session import Challenge, DynamicChallenge, GazePoint
from vericlue_api.services.challenge import generate_challenge

VOICE_PROMPTS = (
    "Hôm nay trời đẹp, tôi đang xác minh danh tính của mình.",
    "Tôi xin xác nhận đây là lần đăng ký tài khoản của chính tôi.",
    "Mùa thu Hà Nội có hoa sữa và gió se lạnh.",
    "Tôi đồng ý cho hệ thống xác minh khuôn mặt và giọng nói của tôi.",
    "Chín mươi tám cộng bảy mươi hai bằng một trăm bảy mươi.",
)
GAZE_DURATION_MS = 7000
GAZE_INTERVAL_MS = 1000
HEAD_DURATION_MS = 6000
MIN_GAZE_AXIS_SPAN = 0.30
PROMPT_WORDS = (
    "mây",
    "sông",
    "núi",
    "biển",
    "rừng",
    "hoa",
    "lá",
    "nắng",
    "gió",
    "trăng",
    "sao",
    "mưa",
    "tre",
    "trúc",
    "sen",
    "đào",
    "mai",
    "cúc",
    "lan",
    "trà",
    "lúa",
    "ngô",
    "thuyền",
    "cầu",
    "đồi",
    "suối",
    "đá",
    "cát",
    "vườn",
    "đường",
    "phố",
    "làng",
)
DIGIT_WORDS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")


def new_voice_prompt(previous: str | None = None) -> str:
    """Use a CSPRNG and guarantee that a reread uses different text."""
    return secrets.choice([text for text in VOICE_PROMPTS if text != previous])


def new_dynamic_voice_prompt(previous: str | None = None) -> str:
    """Compose a short Vietnamese phrase, rather than choose among five fixed recordings."""
    while True:
        words = " ".join(secrets.choice(PROMPT_WORDS) for _ in range(4))
        digits = " ".join(secrets.choice(DIGIT_WORDS) for _ in range(6))
        prompt = f"Tôi xác nhận {words}, mã {digits}."
        if prompt != previous:
            return prompt


def generate_dynamic_challenge(settings: Settings, *, session_id: str, nonce: str) -> Challenge:
    """Keep the shared safe color configuration and append gaze/head capture phases."""
    challenge = generate_challenge(settings)
    challenge.challenge_id = f"ch_{secrets.token_hex(16)}"
    gaze_start = challenge.baseline_ms + sum(
        step.hold_ms + step.transition_ms for step in challenge.color_sequence
    )
    rng = random.SystemRandom()
    # All times share the beginning of the face recording; there is no client clock offset.
    while True:
        points = [GazePoint(x=0.5, y=0.5, at_ms=gaze_start)]
        for offset in range(GAZE_INTERVAL_MS, GAZE_DURATION_MS + 1, GAZE_INTERVAL_MS):
            previous = points[-1]
            while True:
                x, y = rng.randint(20, 80) / 100, rng.randint(20, 80) / 100
                if (x - previous.x) ** 2 + (y - previous.y) ** 2 >= 0.04:
                    break
            points.append(GazePoint(x=x, y=y, at_ms=gaze_start + offset))
        # A near-vertical/horizontal path cannot independently test both gaze axes.
        if all(
            max(getattr(p, axis) for p in points) - min(getattr(p, axis) for p in points)
            >= MIN_GAZE_AXIS_SPAN
            for axis in ("x", "y")
        ):
            break
    turns = ["left", "right"] if secrets.randbelow(2) == 0 else ["right", "left"]
    head_start = gaze_start + GAZE_DURATION_MS
    challenge.dynamic = DynamicChallenge(
        version=1,
        session_id=session_id,
        nonce=nonce,
        gaze_points=points,
        head_turns=[*turns, "center"],
        head_start_at_ms=head_start,
        head_duration_ms=HEAD_DURATION_MS,
        voice_start_at_ms=head_start + HEAD_DURATION_MS,
        voice_prompt=new_dynamic_voice_prompt(),
        voice_challenge_id=f"vc_{secrets.token_hex(16)}",
        frontal_capture_at_ms=challenge.baseline_ms // 2,
    )
    return challenge
