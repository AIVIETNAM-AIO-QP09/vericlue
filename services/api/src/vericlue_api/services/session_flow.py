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
    AccountReceipt,
    ChallengeResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    FinalizeResponse,
    RetryHint,
    Signals,
    VoiceResponse,
)
from vericlue_api.services.account_auth import AccountAuth
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.challenge import generate_challenge
from vericlue_api.services.detection import run_detectors
from vericlue_api.services.dynamic_challenge import (
    VOICE_PROMPTS,
    generate_dynamic_challenge,
    new_dynamic_voice_prompt,
    new_voice_prompt,
)
from vericlue_api.services.file_changes import file_changes
from vericlue_api.services.media_proof import (
    bind_key,
    rejected,
    renew_nonce,
    require_consumed,
    verify_and_consume,
)
from vericlue_api.services.provisional_decision import (
    MAX_VOICE_REREADS,
    Outcome,
)
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import Session, SessionStore
from vericlue_api.services.upload_images import prepare_image
from vericlue_api.services.upload_quota import reserve_media
from vericlue_api.services.uploads import save_upload
from vericlue_ml.common.result import Gate, Module, Status
from vericlue_ml.face.continuity import FACE_VOICE_VERSION
from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION, RECOVERY_MATCH_VERSION
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
        enroll: Callable[[Session], object] | None = None,
        accounts: AccountStore | None = None,
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
        self._enroll = enroll
        self.accounts = accounts or AccountStore(settings, sessions.db)
        self.account_auth = AccountAuth(self.accounts)

    # --- tạo phiên -------------------------------------------------------
    def create(
        self, scenario: str, request: CreateSessionRequest | None = None
    ) -> CreateSessionResponse:
        account_bound = bool(request and request.account_id)
        if request and (
            request.account_id
            and request.purpose == "onboarding"
            or request.device_id
            and (request.purpose != "reauth" or not account_bound)
            or account_bound
            and request.reference_image_id
            or account_bound
            and request.purpose == "recovery"
            and not request.device_public_key_spki
        ):
            raise ApiError(422, "invalid_account_context", "Thông tin phiên chưa phù hợp.")
        if (
            (
                self.settings.require_media_proof
                or self.settings.identity_voice_continuity
                and request is not None
                and request.purpose in {"onboarding", "recovery"}
            )
            and (request is None or not request.device_public_key_spki)
            and not (account_bound and request.purpose == "reauth")
        ):
            raise rejected()
        if request and request.device_public_key_spki and request.purpose == "reauth":
            # A newly supplied public key cannot become a trusted registered device.
            raise ApiError(503, "flow_unavailable", "Luồng xác minh này chưa sẵn sàng.")
        # These flows need gaze/head/match/device verification before real deployment.
        # No environment switch can accidentally enable an incomplete acceptance path.
        if request is not None and self.settings.use_mock_models is not True and not account_bound:
            raise ApiError(503, "flow_unavailable", "Luồng xác minh này chưa sẵn sàng.")
        session = self.sessions.create(
            scenario=scenario,
            challenge=generate_challenge(self.settings),
            ttl_seconds=self.settings.session_ttl_seconds,
            signer=self.settings.session_token_signer,
        )
        session.created_model_mode = (
            "mock"
            if self.settings.use_mock_models is True
            else "real"
            if self.settings.use_mock_models is False
            else "mixed"
        )
        session.result_issuer = self.settings.result_issuer
        session.result_audience = self.settings.result_audience
        device_challenge = None
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
            if request.device_public_key_spki:
                bind_key(session, request.device_public_key_spki)
            if account_bound:
                device_challenge = self.account_auth.bind(
                    session, request.account_id, request.device_id
                )
        return CreateSessionResponse(
            session_id=session.session_id,
            token=session.token,
            expires_at=session.token_expires_at,
            challenge=session.challenge,
            purpose=session.purpose,
            nonce=session.nonce,
            device_challenge=device_challenge,
        )

    def refresh_challenge(self, session: Session) -> ChallengeResponse:
        """Thử thách mới cho phần khuôn mặt và gia hạn token, trong giới hạn tổng (ADR-0017 §2).

        Dùng khi bắt đầu phần khuôn mặt sau giai đoạn A, hoặc làm lại phần khuôn mặt sau khi bị
        gián đoạn. Dữ liệu khuôn mặt và giọng của lượt cũ bị bỏ; số lần chụp lại đã dùng vẫn giữ.
        """
        self.ensure_open(session)
        if session.account_id:
            if session.purpose == "reauth":
                self.account_auth.require_verified(session)
            else:
                self.account_auth.current(session)
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
        renew_nonce(session)
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
        session.voice_video = None
        session.voice_audio_offset_ms = None
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
        if session.account_id:
            if session.purpose == "reauth":
                self.account_auth.require_verified(session)
            else:
                self.account_auth.current(session)
            # L0 is usable independently. Do not accept mock account biometrics or
            # enable the unvalidated real dynamic flow through this new entry point.
            raise ApiError(503, "flow_unavailable", "Luồng xác minh này chưa sẵn sàng.")
        if session.purpose is not None and self.settings.use_mock_models is not True:
            raise ApiError(503, "flow_unavailable", "Luồng xác minh này chưa sẵn sàng.")

    def _requires_proof(self, session: Session) -> bool:
        return (
            bool(session.account_id)
            or self.settings.require_media_proof
            or (
                self.settings.identity_voice_continuity
                and session.purpose in {"onboarding", "recovery"}
            )
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
        media_signature: str | None = None,
    ) -> None:
        """Lưu media sau khi toàn bộ phần tải lên đã được kiểm kích thước."""
        self.ensure_face_step_allowed(session, "media")
        files = {"image": (image_filename, image)}
        if video is not None:
            files["video"] = (video_filename, video)
        verify_and_consume(
            self.sessions.db,
            session,
            "face",
            media_signature,
            files,
            required=self._requires_proof(session),
        )
        prepared = prepare_image(image)
        reserve_media(
            session, self.settings, len(image) + len(prepared.data) + 2 * len(video or b"")
        )
        session.images = [
            save_upload(
                self.settings.media_dir,
                session.session_id,
                "face_image",
                image_filename,
                image,
                privacy=self.privacy,
                image_role=True,
                prepared_image=prepared,
                changes=file_changes(self.sessions.db, self.settings.media_dir),
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
                changes=file_changes(self.sessions.db, self.settings.media_dir),
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
        media_signature: str | None = None,
        audio_offset_ms: int | None = None,
    ) -> Path | None:
        """Chỉ lưu bản ghi của lần đọc được server cho phép."""
        self.ensure_voice_allowed(session)
        files = {"audio": (audio_filename, audio)}
        if video is not None:
            files["video"] = (video_filename, video)
        verify_and_consume(
            self.sessions.db,
            session,
            "voice",
            media_signature,
            files,
            required=self._requires_proof(session),
            audio_offset_ms=audio_offset_ms,
        )
        reserve_media(session, self.settings, 2 * (len(audio) + len(video or b"")))
        session.audio = save_upload(
            self.settings.media_dir,
            session.session_id,
            "voice_audio",
            audio_filename,
            audio,
            privacy=self.privacy,
            changes=file_changes(self.sessions.db, self.settings.media_dir),
        )
        return (
            save_upload(
                self.settings.media_dir,
                session.session_id,
                "voice_video",
                video_filename,
                video,
                privacy=self.privacy,
                changes=file_changes(self.sessions.db, self.settings.media_dir),
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
        require_consumed(self.sessions.db, session, "face", required=self._requires_proof(session))
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
        if session.account_id or s.identity_lab_url and session.purpose != "reauth":
            if session_valid:
                identity = self.account_auth.current(session) if session.account_id else None
                session.results.update(
                    self._run(
                        [Module.FACE_MATCH],
                        session_id=session.session_id,
                        scenario=session.scenario,
                        reference_image=session.id_front,
                        images=session.images[:1],
                        image_roles=["front"],
                        video=session.video,
                        **({"reference_template": identity.template} if identity else {}),
                        extra_metadata={
                            "purpose": session.purpose,
                            "account_id": session.account_id,
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
            renew_nonce(session)
            session.images = []
            session.video = None
            session.audio = None
            session.voice_video = None
            session.voice_audio_offset_ms = None
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
        if status == "pass" and session.purpose == "onboarding" and s.account_enrollment:
            # A clear face finishes onboarding without a sentence: enroll here, as voice() does.
            # The client reads the receipt from GET /account; a failure rolls the decision back.
            if self._enroll is None:
                raise ApiError(503, "enrollment_unavailable", "Chưa thể hoàn tất ghi danh lúc này.")
            self._enroll(session)
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
        continuity_enabled = self.settings.identity_voice_continuity and session.purpose in {
            "onboarding",
            "recovery",
        }
        require_consumed(
            self.sessions.db,
            session,
            "voice",
            required=self.settings.require_media_proof or continuity_enabled,
        )
        if continuity_enabled:
            require_consumed(self.sessions.db, session, "face", required=True)
        session.voice_video = voice_video
        session.voice_audio_offset_ms = audio_offset_ms
        session.results.pop(Module.FACE_CONTINUITY, None)
        session.accepted_steps.append("voice")
        session_valid = self._valid_time(session, voice_challenge=True)
        results = (
            self._run(
                [
                    *self.router.profile.voice_step_modules,
                    *((Module.FACE_CONTINUITY,) if continuity_enabled else ()),
                ],
                session_id=session.session_id,
                scenario=session.scenario,
                images=session.images,
                video=voice_video,
                audio=session.audio,
                **({"reference_video": session.video} if continuity_enabled else {}),
                extra_metadata={
                    "prompt": session.voice_prompt,
                    **(
                        {
                            "expected_challenge": session.challenge.model_dump(
                                mode="json", exclude_none=True
                            ),
                            "expected_voice_challenge_id": session.voice_challenge_id,
                            "account_id": session.account_id,
                            "face_reference_result": session.results[
                                Module.FACE_MATCH
                            ].to_contract()
                            if Module.FACE_MATCH in session.results
                            else None,
                        }
                        if continuity_enabled
                        else {}
                    ),
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
        if session.account_id or self.settings.identity_lab_url and session.purpose != "reauth":
            outcome = self._identity_gate(session, outcome)
        if continuity_enabled:
            outcome = self._continuity_gate(session, outcome)
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
        receipt = None
        if (
            outcome.status == "pass"
            and session.purpose == "onboarding"
            and self.settings.account_enrollment
        ):
            if self._enroll is None:
                raise ApiError(503, "enrollment_unavailable", "Chưa thể hoàn tất ghi danh lúc này.")
            receipt = self._enroll(session)
        if outcome.status == "pass" and session.purpose == "recovery" and session.account_id:
            receipt = self.accounts.recover(session)
        return VoiceResponse(
            status=outcome.status,
            account=AccountReceipt.model_validate(receipt) if receipt is not None else None,
        )

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
        session.results.pop(Module.FACE_CONTINUITY, None)
        session.voice_video = None
        session.voice_audio_offset_ms = None
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
            (RECOVERY_MATCH_VERSION if session.purpose == "recovery" else REAUTH_MATCH_VERSION)
            if session.account_id
            else VIDEO_MATCH_VERSION
            if self.settings.identity_face_from_video
            else MATCH_VERSION
        )
        if match is not None and match.model_version == expected_version:
            threshold = match.quality.get("threshold_cosine")
            if type(threshold) in (int, float) and -1 <= threshold <= 1:
                thresholds["identity_face_cosine"] = threshold
        allowed = (
            (
                bool(session.account_id)
                or (
                    session.id_confirmed
                    and not session.id_edited
                    and session.id_source in {"server_qr", "ocr"}
                )
            )
            and match is not None
            and match.model_version == expected_version
            and match.status == Status.OK
            and match.error_code is None
            and match.gate == Gate.PASS
            and (
                not session.account_id
                or (
                    match.quality.get("enrolled_reference") is True
                    and [e.value for e in match.evidence if e.name == "reference_account_id"]
                    == [session.account_id]
                )
            )
            and (
                not self.settings.identity_consistency_required
                or session.purpose == "reauth"
                and bool(session.account_id)
                or match.quality.get("consistency_verified") is True
            )
        )
        if not allowed and outcome.status in {"pass", "voice_challenge"}:
            return replace(
                outcome, status="review", reason="identity requires review", thresholds=thresholds
            )
        return replace(outcome, thresholds=thresholds)

    @staticmethod
    def _continuity_gate(session: Session, outcome):
        result = session.results.get(Module.FACE_CONTINUITY)
        reference = session.results.get(Module.FACE_MATCH)
        source = (
            [e.value for e in reference.evidence if e.name == "source_video_sha256"]
            if reference
            else []
        )
        expected = {
            "challenge_id": [session.challenge.challenge_id],
            "voice_challenge_id": [session.voice_challenge_id],
            "source_video_sha256": source,
        }
        allowed = (
            result is not None
            and result.module == Module.FACE_CONTINUITY
            and result.model_version == FACE_VOICE_VERSION
            and result.status == Status.OK
            and result.error_code is None
            and result.gate == Gate.PASS
            and len(source) == 1
            and all(
                [e.value for e in result.evidence if e.name == name] == values
                for name, values in expected.items()
            )
        )
        if not allowed and outcome.status in {"pass", "voice_challenge"}:
            return replace(outcome, status="review", reason="voice identity requires review")
        return outcome

    @staticmethod
    def _case_notes(session: Session) -> list[str]:
        notes = [f"Chụp lại {session.retries_used} lần"] if session.retries_used else []
        if session.id_edited:
            notes.append(
                "Người dùng sửa thông tin CCCD khác bản quét: " + ", ".join(session.id_edited)
            )
        return notes

    def _open_case(self, session: Session, outcome: Outcome) -> None:
        if self.settings.product_mode == "ekyc":
            # The caller completes this unverified session without inventing staff action.
            return
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
