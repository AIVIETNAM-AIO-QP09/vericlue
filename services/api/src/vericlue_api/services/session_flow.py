"""Luồng một phiên eKYC (kiến trúc §6). Router chỉ gọi các hàm ở đây.

Giai đoạn PLAT-04: chưa có máy trạng thái chống phát lại, HMAC, TTL hay 409 (PLAT-06),
chưa có DB (PLAT-05), chưa chạy song song (PLAT-08), luật quyết định là luật TẠM.
"""

from __future__ import annotations

import random

from vericlue_api.core.config import Settings
from vericlue_api.schemas.review import MediaRef
from vericlue_api.schemas.session import (
    CreateSessionResponse,
    FinalizeResponse,
    Signals,
    VoiceResponse,
)
from vericlue_api.services.challenge import generate_challenge
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.provisional_decision import (
    FINALIZE_MODULES,
    MAX_VOICE_REREADS,
    VOICE_STEP_MODULES,
    Outcome,
    decide_finalize,
    decide_voice,
)
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_store import Session, SessionStore
from vericlue_ml.common.result import Module

VOICE_PROMPTS = (
    "Hôm nay trời đẹp, tôi đang xác minh danh tính của mình.",
    "Tôi xin xác nhận đây là lần đăng ký tài khoản của chính tôi.",
    "Mùa thu Hà Nội có hoa sữa và gió se lạnh.",
    "Tôi đồng ý cho hệ thống xác minh khuôn mặt và giọng nói của tôi.",
    "Chín mươi tám cộng bảy mươi hai bằng một trăm bảy mươi.",
)


class SessionFlow:
    def __init__(self, settings: Settings, sessions: SessionStore, reviews: ReviewStore) -> None:
        self.settings = settings
        self.sessions = sessions
        self.reviews = reviews

    # --- tạo phiên -------------------------------------------------------
    def create(self, scenario: str) -> CreateSessionResponse:
        session = self.sessions.create(
            scenario=scenario,
            challenge=generate_challenge(self.settings),
            ttl_seconds=self.settings.session_ttl_seconds,
        )
        return CreateSessionResponse(
            session_id=session.session_id,
            token=session.token,
            expires_at=session.token_expires_at,
            challenge=session.challenge,
        )

    # --- tải lên ---------------------------------------------------------
    def accept_signals(self, session: Session, signals: Signals) -> None:
        session.signals = signals.model_dump(mode="json")

    # --- finalize --------------------------------------------------------
    def finalize(self, session: Session) -> FinalizeResponse:
        results = run_detectors(
            FINALIZE_MODULES,
            session_id=session.session_id,
            scenario=session.scenario,
            images=session.images,
            video=session.video,
            signals=session.signals,
            extra_metadata={"challenge_id": session.challenge.challenge_id},
        )
        session.results.update(results)
        s = self.settings
        outcome = decide_finalize(
            results,
            retries_used=session.retries_used,
            max_retries=s.max_retries,
            b=s.provisional_threshold_b,
            a=s.provisional_threshold_a,
        )
        if outcome.status == "retry":
            session.retries_used += 1
            session.challenge = generate_challenge(s)  # lượt mới, thử thách mới
            return FinalizeResponse(
                status="retry",
                retry_hint=outcome.retry_hint,  # type: ignore[arg-type]
                attempts_left=s.max_retries - session.retries_used,
                challenge=session.challenge,
            )
        if outcome.status == "voice_challenge":
            return FinalizeResponse(
                status="voice_challenge",
                voice_prompt=self._new_prompt(session),
                attempts_left=MAX_VOICE_REREADS,
            )
        if outcome.status == "review":
            self._open_case(session, outcome)
        return FinalizeResponse(status=outcome.status)

    # --- voice -----------------------------------------------------------
    def voice(self, session: Session) -> VoiceResponse:
        results = run_detectors(
            VOICE_STEP_MODULES,
            session_id=session.session_id,
            scenario=session.scenario,
            images=session.images,
            video=session.video,
            audio=session.audio,
            extra_metadata={"prompt": session.voice_prompt},
        )
        session.results.update(results)
        outcome = decide_voice(
            results,
            rereads_used=session.voice_rereads_used,
            b=self.settings.provisional_threshold_b,
        )
        if outcome.status == "voice_challenge":
            session.voice_rereads_used += 1
            return VoiceResponse(
                status="voice_challenge",
                voice_prompt=self._new_prompt(session),
                attempts_left=MAX_VOICE_REREADS - session.voice_rereads_used,
            )
        if outcome.status == "review":
            self._open_case(session, outcome)
            return VoiceResponse(status="review")
        return VoiceResponse(status="pass")

    # --- nội bộ ----------------------------------------------------------
    @staticmethod
    def _new_prompt(session: Session) -> str:
        choices = [p for p in VOICE_PROMPTS if p != session.voice_prompt]
        session.voice_prompt = random.SystemRandom().choice(choices)
        return session.voice_prompt

    def _open_case(self, session: Session, outcome: Outcome) -> None:
        if session.case_id is not None:  # một phiên chỉ một ca
            return
        media = [MediaRef(kind="face_image", url=f"/media/{session.session_id}/face_image")]
        if session.video is not None:
            media.append(MediaRef(kind="face_video", url=f"/media/{session.session_id}/face_video"))
        if session.audio is not None:
            media.append(
                MediaRef(kind="voice_audio", url=f"/media/{session.session_id}/voice_audio")
            )
        record = self.reviews.add(
            session_id=session.session_id,
            priority=outcome.priority,
            scenario=session.scenario,
            results=dict(session.results),
            media=media,
            notes=[f"Chụp lại {session.retries_used} lần"] if session.retries_used else [],
        )
        session.case_id = record.case_id


__all__ = ["Module", "SessionFlow", "VOICE_PROMPTS"]
