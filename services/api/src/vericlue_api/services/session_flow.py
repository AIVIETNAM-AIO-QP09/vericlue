"""Luồng một phiên eKYC (kiến trúc §6). Router chỉ gọi các hàm ở đây.

PLAT-06: mỗi bước chỉ nhận một lần, token có thời hạn và kết quả cuối đóng phiên.
ROUT-02 dùng TrustRouter; ngưỡng/fusion còn provisional.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
from vericlue_api.services.uploads import save_upload
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
            signer=self.settings.session_token_signer,
        )
        return CreateSessionResponse(
            session_id=session.session_id,
            token=session.token,
            expires_at=session.token_expires_at,
            challenge=session.challenge,
        )

    # --- tải lên ---------------------------------------------------------
    def accept_media(
        self,
        session: Session,
        *,
        image: bytes,
        image_filename: str | None,
        video: bytes | None = None,
        video_filename: str | None = None,
    ) -> None:
        """Lưu media sau khi toàn bộ phần tải lên đã được kiểm kích thước."""
        self.ensure_face_step_allowed(session, "media")
        session.images = [
            save_upload(
                self.settings.media_dir, session.session_id, "face_image", image_filename, image
            )
        ]
        session.video = (
            save_upload(
                self.settings.media_dir, session.session_id, "face_video", video_filename, video
            )
            if video is not None
            else None
        )
        session.accepted_steps.append("media")

    def accept_voice_media(
        self,
        session: Session,
        *,
        audio: bytes,
        audio_filename: str | None,
        video: bytes | None = None,
        video_filename: str | None = None,
    ) -> Path | None:
        """Chỉ lưu bản ghi của lần đọc được server cho phép."""
        self.ensure_voice_allowed(session)
        session.audio = save_upload(
            self.settings.media_dir, session.session_id, "voice_audio", audio_filename, audio
        )
        return (
            save_upload(
                self.settings.media_dir, session.session_id, "voice_video", video_filename, video
            )
            if video is not None
            else None
        )

    def accept_signals(self, session: Session, signals: Signals) -> None:
        self.ensure_face_step_allowed(session, "signals")
        session.signals = signals.model_dump(mode="json")
        session.accepted_steps.append("signals")

    def ensure_face_step_allowed(self, session: Session, step: str) -> None:
        """Kiểm trước khi nhận media hoặc chạy detector của lượt khuôn mặt."""
        self.ensure_open(session)
        if session.voice_requested:
            raise ApiError(409, "step_not_allowed", "Vui lòng hoàn thành bước đọc câu.")
        if step in session.accepted_steps:
            raise ApiError(409, "step_already_received", "Bước này đã được tiếp nhận.")
        if session.challenge.expires_at is None or not self._valid_time(
            session, color_challenge=True
        ):
            raise ApiError(409, "challenge_expired", "Lượt xác minh đã hết hạn.")

    @staticmethod
    def _valid_time(
        session: Session,
        *,
        color_challenge: bool = False,
        voice_challenge: bool = False,
    ) -> bool:
        now = datetime.now(UTC)
        deadlines = [session.token_expires_at]
        if color_challenge and session.challenge.expires_at is not None:
            deadlines.append(session.challenge.expires_at)
        if voice_challenge:
            if session.voice_expires_at is None:
                return False
            deadlines.append(session.voice_expires_at)
        # Legacy snapshots may be naive UTC; never compare naive to aware datetime.
        return all((d.replace(tzinfo=UTC) if d.tzinfo is None else d) > now for d in deadlines)

    # --- finalize --------------------------------------------------------
    @staticmethod
    def ensure_open(session: Session) -> None:
        """Cả pass và review là kết quả cuối của phiên."""
        if session.case_id is not None or session.completed:
            raise ApiError(409, "session_closed", "Phiên đã kết thúc.")

    def ensure_voice_allowed(self, session: Session) -> None:
        """Chỉ nhận giọng nói khi finalize vừa yêu cầu; không thì là đường tắt tới `pass`."""
        self.ensure_open(session)
        if not session.voice_requested:
            raise ApiError(409, "voice_not_requested", "Chưa có yêu cầu đọc câu cho phiên này.")
        if "voice" in session.accepted_steps:
            raise ApiError(409, "step_already_received", "Bước này đã được tiếp nhận.")
        expiry = session.voice_expires_at
        if expiry is None or (
            expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry
        ) <= datetime.now(UTC):
            raise ApiError(409, "challenge_expired", "Lượt xác minh đã hết hạn.")

    def finalize(self, session: Session) -> FinalizeResponse:
        self.ensure_face_step_allowed(session, "finalize")
        session.accepted_steps.append("finalize")
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
            # A retry must never reuse evidence/results from the previous capture.
            session.images = []
            session.video = None
            session.audio = None
            session.signals = {}
            session.results = {}
            session.accepted_steps = []
            session.voice_prompt = None
            session.voice_expires_at = None
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
        session.completed = True
        return FinalizeResponse(status=outcome.status)

    # --- voice -----------------------------------------------------------
    def voice(self, session: Session, *, voice_video: Path | None = None) -> VoiceResponse:
        self.ensure_voice_allowed(session)
        session.accepted_steps.append("voice")
        session_valid = self._valid_time(session, voice_challenge=True)
        results = (
            self._run(
                self.router.profile.voice_step_modules,
                session_id=session.session_id,
                scenario=session.scenario,
                images=session.images,
                video=voice_video,
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
            session_valid=session_valid and self._valid_time(session, voice_challenge=True),
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
            session.accepted_steps.remove("voice")  # A fresh prompt grants one new voice attempt.
            return VoiceResponse(
                status="voice_challenge",
                voice_prompt=self._new_prompt(session),
                attempts_left=MAX_VOICE_REREADS - session.voice_rereads_used,
            )
        session.voice_requested = False  # kết thúc bước giọng nói
        session.completed = True
        if outcome.status == "review":
            self._open_case(session, outcome)
            return VoiceResponse(status="review")
        return VoiceResponse(status="pass")

    # --- nội bộ ----------------------------------------------------------
    def _new_prompt(self, session: Session) -> str:
        choices = [p for p in VOICE_PROMPTS if p != session.voice_prompt]
        session.voice_prompt = random.SystemRandom().choice(choices)
        session.voice_expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.challenge_ttl_seconds,
        )
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
