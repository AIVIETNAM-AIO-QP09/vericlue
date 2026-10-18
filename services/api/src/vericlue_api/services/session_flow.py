"""Luồng một phiên eKYC (kiến trúc §6). Router chỉ gọi các hàm ở đây.

Giai đoạn PLAT-04: chưa có máy trạng thái chống phát lại "mỗi bước một lần mỗi lượt" (409), HMAC,
TTL token HMAC hay 429 (PLAT-06); DB/transaction và inference song song đã có (PLAT-05/08).
ROUT-02 dùng TrustRouter và kiểm deadline đã lưu; ngưỡng/fusion còn provisional.
Chỉ kiểm THỨ TỰ luồng để không có đường tắt tới `pass`: 409 `session_closed` khi phiên đã vào bàn
duyệt, 409 `voice_not_requested` khi `finalize` chưa yêu cầu đọc câu.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import get_args

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.schemas.review import MediaRef
from vericlue_api.schemas.session import (
    CreateSessionResponse,
    FinalizeResponse,
    RetryHint,
    Signals,
    VoiceResponse,
)
from vericlue_api.services.challenge import generate_challenge
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.provisional_decision import (
    MAX_VOICE_REREADS,
    Outcome,
)
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_store import Session, SessionStore
from vericlue_ml.common.result import Module
from vericlue_ml.router.policy import TrustRouter

VOICE_PROMPTS = (
    "Hôm nay trời đẹp, tôi đang xác minh danh tính của mình.",
    "Tôi xin xác nhận đây là lần đăng ký tài khoản của chính tôi.",
    "Mùa thu Hà Nội có hoa sữa và gió se lạnh.",
    "Tôi đồng ý cho hệ thống xác minh khuôn mặt và giọng nói của tôi.",
    "Chín mươi tám cộng bảy mươi hai bằng một trăm bảy mươi.",
)


RETRY_HINTS = frozenset(get_args(RetryHint))
DEFAULT_HINT = "MORE_LIGHT"


class SessionFlow:
    def __init__(
        self,
        settings: Settings,
        sessions: SessionStore,
        reviews: ReviewStore,
        *,
        runner: Callable = run_detectors,
        router: TrustRouter | None = None,
    ) -> None:
        self.router = (
            router
            if router is not None
            else TrustRouter(settings.router_config, profile=settings.router_profile)
        )
        self.settings = settings
        self._run = runner
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

    @staticmethod
    def _valid_time(session: Session, *, color_challenge: bool = False) -> bool:
        now = datetime.now(UTC)
        deadlines = [session.token_expires_at]
        if color_challenge and session.challenge.expires_at is not None:
            deadlines.append(session.challenge.expires_at)
        # Legacy snapshots may be naive UTC; never compare naive to aware datetime.
        return all((d.replace(tzinfo=UTC) if d.tzinfo is None else d) > now for d in deadlines)

    # --- finalize --------------------------------------------------------
    @staticmethod
    def ensure_open(session: Session) -> None:
        """Phiên đã vào bàn duyệt là trạng thái cuối: không nhận thêm finalize hay voice."""
        if session.case_id is not None:
            raise ApiError(409, "session_closed", "Phiên đã chuyển sang bàn duyệt.")

    def ensure_voice_allowed(self, session: Session) -> None:
        """Chỉ nhận giọng nói khi finalize vừa yêu cầu; không thì là đường tắt tới `pass`."""
        self.ensure_open(session)
        if not session.voice_requested:
            raise ApiError(409, "voice_not_requested", "Chưa có yêu cầu đọc câu cho phiên này.")

    def finalize(self, session: Session) -> FinalizeResponse:
        self.ensure_open(session)
        session.voice_requested = False  # chỉ bật lại nếu lần này ra voice_challenge
        session_valid = self._valid_time(session, color_challenge=True)
        results = (
            self._run(
                self.router.profile.finalize_modules,
                session_id=session.session_id,
                scenario=session.scenario,
                images=session.images,
                video=session.video,
                signals=session.signals,
                extra_metadata={"challenge_id": session.challenge.challenge_id},
            )
            if session_valid
            else {}
        )
        session.results.update(results)
        s = self.settings
        outcome = self.router.finalize(
            results,
            retries_used=session.retries_used,
            max_retries=s.max_retries,
            session_valid=session_valid and self._valid_time(session, color_challenge=True),
        )
        session.results.update(outcome.results)
        self.sessions.record_decision(
            session,
            outcome.status,
            thresholds=outcome.thresholds,
            config_version=outcome.config_version,
        )
        if outcome.status == "retry":
            hint = outcome.retry_hint if outcome.retry_hint in RETRY_HINTS else DEFAULT_HINT
            session.retries_used += 1
            session.challenge = generate_challenge(s)  # lượt mới, thử thách mới
            return FinalizeResponse(
                status="retry",
                retry_hint=hint,  # type: ignore[arg-type]
                attempts_left=s.max_retries - session.retries_used,
                challenge=session.challenge,
            )
        if outcome.status == "voice_challenge":
            session.voice_requested = True
            session.voice_rereads_used = 0  # yêu cầu đọc câu mới
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
        self.ensure_voice_allowed(session)
        session_valid = self._valid_time(session)
        results = (
            self._run(
                self.router.profile.voice_step_modules,
                session_id=session.session_id,
                scenario=session.scenario,
                images=session.images,
                video=session.video,
                audio=session.audio,
                extra_metadata={"prompt": session.voice_prompt},
            )
            if session_valid
            else {}
        )
        session.results.update(results)
        outcome = self.router.voice(
            results,
            rereads_used=session.voice_rereads_used,
            session_valid=session_valid and self._valid_time(session),
        )
        session.results.update(outcome.results)
        self.sessions.record_decision(
            session,
            outcome.status,
            thresholds=outcome.thresholds,
            config_version=outcome.config_version,
        )
        if outcome.status == "voice_challenge":
            session.voice_rereads_used += 1
            return VoiceResponse(
                status="voice_challenge",
                voice_prompt=self._new_prompt(session),
                attempts_left=MAX_VOICE_REREADS - session.voice_rereads_used,
            )
        session.voice_requested = False  # kết thúc bước giọng nói
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
