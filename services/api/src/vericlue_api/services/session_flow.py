"""Luồng một phiên eKYC (kiến trúc §6). Router chỉ gọi các hàm ở đây.

PLAT-06: mỗi bước chỉ nhận một lần, token có thời hạn và kết quả cuối đóng phiên.
ROUT-02 dùng TrustRouter; ngưỡng/fusion còn provisional.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_args

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.core.session_tokens import token_digest
from vericlue_api.schemas.review import MediaRef
from vericlue_api.schemas.session import (
    ChallengeResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    FinalizeResponse,
    RetryHint,
    Signals,
    VoiceResponse,
)
from vericlue_api.services.challenge import generate_challenge
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.dynamic_challenge import (
    VOICE_PROMPTS,
    generate_dynamic_challenge,
    new_dynamic_voice_prompt,
    new_voice_prompt,
)
from vericlue_api.services.provisional_decision import (
    MAX_VOICE_REREADS,
    Outcome,
)
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import Session, SessionStore
from vericlue_api.services.uploads import save_upload
from vericlue_ml.common.result import Gate, Module, Status
from vericlue_ml.face.match import MATCH_VERSION
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION
from vericlue_ml.router.flows import route_face, route_voice
from vericlue_ml.router.policy import TrustRouter

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
        privacy: SessionPrivacy | None = None,
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
        self.privacy = privacy

    # --- tạo phiên -------------------------------------------------------
    def create(
        self, scenario: str, request: CreateSessionRequest | None = None
    ) -> CreateSessionResponse:
        # These flows need gaze/head/match/device verification before real deployment.
        # No environment switch can accidentally enable an incomplete acceptance path.
        if request is not None and self.settings.use_mock_models is not True:
            raise ApiError(503, "flow_unavailable", "Luồng xác minh này chưa sẵn sàng.")
        session = self.sessions.create(
            scenario=scenario,
            challenge=generate_challenge(self.settings),
            ttl_seconds=self.settings.session_ttl_seconds,
            signer=self.settings.session_token_signer,
        )
        if request is not None:
            session.purpose = request.purpose
            session.nonce = request.nonce
            session.reference_image_id = request.reference_image_id
            if request.purpose in {"onboarding", "recovery"}:
                session.challenge = generate_dynamic_challenge(
                    self.settings, session_id=session.session_id, nonce=request.nonce
                )
                session.voice_prompt = session.challenge.dynamic.voice_prompt
                session.voice_challenge_id = session.challenge.dynamic.voice_challenge_id
        return CreateSessionResponse(
            session_id=session.session_id,
            token=session.token,
            expires_at=session.token_expires_at,
            challenge=session.challenge,
            purpose=session.purpose,
            nonce=session.nonce,
        )

    def refresh_challenge(self, session: Session) -> ChallengeResponse:
        """Thử thách mới cho phần khuôn mặt và gia hạn token, trong giới hạn tổng (ADR-0017 §2).

        Dùng khi bắt đầu phần khuôn mặt sau giai đoạn A, hoặc làm lại phần khuôn mặt sau khi bị
        gián đoạn. Dữ liệu khuôn mặt và giọng của lượt cũ bị bỏ; số lần chụp lại đã dùng vẫn giữ.
        """
        self.ensure_open(session)
        now = datetime.now(UTC)
        started = session.created_at or now
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        end = started + timedelta(seconds=self.settings.session_max_seconds)
        if now >= end:
            raise ApiError(
                409, "session_too_long", "Phiên đã quá thời gian cho phép. Hãy bắt đầu lại."
            )
        if session.face_scored:
            # Bỏ một lượt đã chấm (không phải retry) cũng là một lần chụp lại: không chấm lại vô hạn.
            session.retries_used += 1
            session.face_scored = False
        # Same as a retry: a whole new pack (LIVE-01 `dynamic` included) with new attempt IDs.
        session.challenge = (
            generate_dynamic_challenge(
                self.settings, session_id=session.session_id, nonce=session.nonce
            )
            if session.challenge.dynamic is not None
            else generate_challenge(self.settings)
        )
        # The token carries its own signed expiry (PLAT-06): extending means issuing a new one.
        session.token_expires_at = min(
            now + timedelta(seconds=self.settings.session_ttl_seconds), end
        )
        token = self.settings.session_token_signer.issue(
            session.session_id, session.token_expires_at
        )
        session.token_hash = token_digest(token)
        session.images = []
        session.video = None
        session.audio = None
        session.signals = {}
        session.results = {}
        session.accepted_steps = []
        session.voice_requested = False
        dynamic = session.challenge.dynamic
        session.voice_prompt = dynamic.voice_prompt if dynamic else None
        session.voice_challenge_id = dynamic.voice_challenge_id if dynamic else None
        session.voice_expires_at = None
        return ChallengeResponse(
            token=token, expires_at=session.token_expires_at, challenge=session.challenge
        )

    def ensure_binding(
        self, session: Session, challenge_id: str | None, *, voice: bool = False
    ) -> None:
        """An identifier binds a request to an attempt, not to signed camera bytes (LIVE-03)."""
        if session.purpose is None:
            return
        self.ensure_flow_available(session)
        expected = session.voice_challenge_id if voice else session.challenge.challenge_id
        if (
            not challenge_id
            or not expected
            or not secrets.compare_digest(challenge_id.encode("utf-8"), expected.encode("utf-8"))
        ):
            raise ApiError(409, "challenge_mismatch", "Lượt xác minh không còn phù hợp.")

    def ensure_flow_available(self, session: Session) -> None:
        """A saved mock session must not become usable after switching the server to real."""
        if session.purpose is not None and self.settings.use_mock_models is not True:
            raise ApiError(503, "flow_unavailable", "Luồng xác minh này chưa sẵn sàng.")

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
                self.settings.media_dir,
                session.session_id,
                "face_image",
                image_filename,
                image,
                privacy=self.privacy,
            )
        ]
        session.video = (
            save_upload(
                self.settings.media_dir,
                session.session_id,
                "face_video",
                video_filename,
                video,
                privacy=self.privacy,
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
            self.settings.media_dir,
            session.session_id,
            "voice_audio",
            audio_filename,
            audio,
            privacy=self.privacy,
        )
        return (
            save_upload(
                self.settings.media_dir,
                session.session_id,
                "voice_video",
                video_filename,
                video,
                privacy=self.privacy,
            )
            if video is not None
            else None
        )

    def accept_signals(self, session: Session, signals: Signals) -> None:
        self.ensure_face_step_allowed(session, "signals")
        session.signals = signals.model_dump(mode="json", exclude_none=True)
        session.accepted_steps.append("signals")

    def ensure_face_step_allowed(self, session: Session, step: str) -> None:
        """Kiểm trước khi nhận media hoặc chạy detector của lượt khuôn mặt."""
        self.ensure_flow_available(session)
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
        self.ensure_flow_available(session)
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

    def finalize(self, session: Session, challenge_id: str | None = None) -> FinalizeResponse:
        self.ensure_binding(session, challenge_id)
        self.ensure_face_step_allowed(session, "finalize")
        if session.purpose is not None and not {"media", "signals"}.issubset(
            session.accepted_steps
        ):
            raise ApiError(409, "steps_incomplete", "Vui lòng hoàn thành bước ghi hình.")
        session.accepted_steps.append("finalize")
        session.voice_requested = False  # chỉ bật lại nếu lần này ra voice_challenge
        session_valid = self._valid_time(session, color_challenge=True)
        results = (
            self._run(
                [
                    *self.router.profile.finalize_modules,
                    *(
                        (Module.GAZE_TRACKING, Module.HEAD_TURN)
                        if self.settings.session_face_checks and session.purpose != "reauth"
                        else ()
                    ),
                ],
                session_id=session.session_id,
                scenario=session.scenario,
                images=session.images,
                video=session.video,
                signals=session.signals,
                extra_metadata={
                    "challenge_id": session.challenge.challenge_id,
                    **(
                        {
                            "expected_challenge": session.challenge.model_dump(
                                mode="json", exclude_none=True
                            ),
                            "purpose": session.purpose,
                            "reference_image_id": session.reference_image_id,
                        }
                        if session.purpose is not None
                        else {}
                    ),
                },
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
        outcome = route_face(outcome, session.purpose, device_verified=session.device_verified)
        # This bridge compares a newly scanned card. Reauth uses enrolled identity/device
        # context (FLOW-05/SEC-02), not a fresh CCCD or the staff-review card gate.
        if s.identity_lab_url and session.purpose != "reauth":
            if session_valid:
                session.results.update(
                    self._run(
                        [Module.FACE_MATCH],
                        session_id=session.session_id,
                        scenario=session.scenario,
                        reference_image=session.id_front,
                        images=session.images[:1],
                        image_roles=["front"],
                        video=session.video,
                        extra_metadata={
                            "challenge_id": session.challenge.challenge_id,
                            "expected_challenge": session.challenge.model_dump(
                                mode="json", exclude_none=True
                            ),
                        },
                    )
                )
            outcome = self._identity_gate(session, outcome)
            if not self._valid_time(session, color_challenge=True) and outcome.status in {
                "pass",
                "voice_challenge",
            }:
                outcome = replace(outcome, status="review", reason="identity inference expired")
        if s.session_face_checks and session.purpose != "reauth":
            motion_ok = all(
                (measured := session.results.get(module)) is not None
                and measured.status == Status.OK
                and measured.gate == Gate.PASS
                for module in (Module.GAZE_TRACKING, Module.HEAD_TURN)
            )
            if not motion_ok and outcome.status in {"pass", "voice_challenge"}:
                outcome = replace(outcome, status="review", reason="motion checks incomplete")
        session.results.update(outcome.results)
        status = outcome.status
        if status == "pass" and session.voice_owed:
            # Lượt mặt mới (sau POST /challenge) không xóa yêu cầu đọc câu của lượt trước.
            status = "voice_challenge"
        self.sessions.record_decision(
            session,
            status,
            thresholds=outcome.thresholds,
            config_version=outcome.config_version,
        )
        session.face_scored = status != "retry"
        if status == "retry":
            hint = outcome.retry_hint if outcome.retry_hint in RETRY_HINTS else DEFAULT_HINT
            session.retries_used += 1
            session.challenge = (
                generate_dynamic_challenge(s, session_id=session.session_id, nonce=session.nonce)
                if session.challenge.dynamic is not None
                else generate_challenge(s)
            )
            # A retry must never reuse evidence/results from the previous capture.
            session.images = []
            session.video = None
            session.audio = None
            session.signals = {}
            session.results = {}
            session.accepted_steps = []
            dynamic = session.challenge.dynamic
            session.voice_prompt = dynamic.voice_prompt if dynamic else None
            session.voice_challenge_id = dynamic.voice_challenge_id if dynamic else None
            session.voice_expires_at = None
            return FinalizeResponse(
                status="retry",
                retry_hint=hint,  # type: ignore[arg-type]
                attempts_left=s.max_retries - session.retries_used,
                challenge=session.challenge,
            )
        if status == "voice_challenge":
            session.voice_requested = True
            session.voice_owed = True
            session.voice_rereads_used = 0  # yêu cầu đọc câu mới
            return FinalizeResponse(
                status="voice_challenge",
                voice_prompt=self._start_voice(session),
                attempts_left=MAX_VOICE_REREADS,
                voice_challenge_id=session.voice_challenge_id,
            )
        if status == "review":
            self._open_case(session, outcome)
        session.completed = True
        return FinalizeResponse(status=status)  # type: ignore[arg-type]

    # --- voice -----------------------------------------------------------
    def voice(
        self,
        session: Session,
        *,
        voice_video: Path | None = None,
        audio_offset_ms: int | None = None,
    ) -> VoiceResponse:
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
                extra_metadata={
                    "prompt": session.voice_prompt,
                    # Khi WAV bắt đầu, tính từ khung hình đầu của video (app Android).
                    **({"audio_offset_ms": audio_offset_ms} if audio_offset_ms is not None else {}),
                    **(
                        {
                            "voice_challenge_id": session.voice_challenge_id,
                            "challenge_id": session.challenge.challenge_id,
                            "purpose": session.purpose,
                        }
                        if session.purpose is not None
                        else {}
                    ),
                },
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
        outcome = route_voice(outcome, session.purpose)
        if self.settings.identity_lab_url and session.purpose != "reauth":
            outcome = self._identity_gate(session, outcome)
        if outcome.status != "voice_challenge":
            session.voice_owed = False
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
                voice_challenge_id=session.voice_challenge_id,
            )
        session.voice_requested = False  # kết thúc bước giọng nói
        session.completed = True
        if outcome.status == "review":
            self._open_case(session, outcome)
            return VoiceResponse(status="review")
        return VoiceResponse(status=outcome.status)

    # --- nội bộ ----------------------------------------------------------
    def _start_voice(self, session: Session) -> str:
        # A preissued prompt lets clients record while finalize is still running.
        if session.challenge.dynamic is None:
            return self._new_prompt(session)
        session.voice_prompt = session.challenge.dynamic.voice_prompt
        session.voice_challenge_id = session.challenge.dynamic.voice_challenge_id
        session.voice_expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.challenge_ttl_seconds,
        )
        return session.voice_prompt

    def _new_prompt(self, session: Session) -> str:
        session.voice_prompt = (
            new_dynamic_voice_prompt(session.voice_prompt)
            if session.purpose is not None
            else new_voice_prompt(session.voice_prompt)
        )
        if session.purpose is not None:
            session.voice_challenge_id = f"vc_{secrets.token_hex(16)}"
        session.voice_expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.challenge_ttl_seconds,
        )
        return session.voice_prompt

    def _identity_gate(self, session: Session, outcome):
        """A face match is one required signal, never an override of PAD or voice failures."""
        match = session.results.get(Module.FACE_MATCH)
        thresholds = dict(outcome.thresholds)
        expected_version = (
            VIDEO_MATCH_VERSION if self.settings.identity_face_from_video else MATCH_VERSION
        )
        if match is not None and match.model_version == expected_version:
            threshold = match.quality.get("threshold_cosine")
            if type(threshold) in (int, float) and -1 <= threshold <= 1:
                thresholds["identity_face_cosine"] = threshold
        allowed = (
            session.id_confirmed
            and not session.id_edited
            and session.id_source in {"server_qr", "ocr"}
            and match is not None
            and match.model_version == expected_version
            and match.status == Status.OK
            and match.gate == Gate.PASS
            and (
                not self.settings.identity_consistency_required
                or match.quality.get("consistency_verified") is True
            )
        )
        if not allowed and outcome.status in {"pass", "voice_challenge"}:
            return replace(
                outcome, status="review", reason="identity requires review", thresholds=thresholds
            )
        return replace(outcome, thresholds=thresholds)

    @staticmethod
    def _case_notes(session: Session) -> list[str]:
        notes = [f"Chụp lại {session.retries_used} lần"] if session.retries_used else []
        if session.id_edited:
            notes.append(
                "Người dùng sửa thông tin CCCD khác bản quét: " + ", ".join(session.id_edited)
            )
        return notes

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
            notes=self._case_notes(session),
        )
        session.case_id = record.case_id


__all__ = ["Module", "SessionFlow", "VOICE_PROMPTS"]
