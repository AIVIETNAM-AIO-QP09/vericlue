"""Luồng một phiên eKYC (kiến trúc §6). Router chỉ gọi các hàm ở đây.

PLAT-06: mỗi bước chỉ nhận một lần, token có thời hạn và kết quả cuối đóng phiên.
ROUT-02 dùng TrustRouter; ngưỡng/fusion còn provisional.
"""

from __future__ import annotations

import math
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
from vericlue_api.services.privacy_consent import require_categories
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
from vericlue_ml.common.calibration import CalibrationError, Calibrator
from vericlue_ml.common.result import ErrorCode, Evidence, Gate, Module, Status
from vericlue_ml.face.continuity import FACE_VOICE_VERSION
from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION, RECOVERY_MATCH_VERSION
from vericlue_ml.face.match import MATCH_VERSION, MatchThreshold
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION
from vericlue_ml.presence.head_protocol import session_model_version
from vericlue_ml.router.flows import route_face, route_voice
from vericlue_ml.router.policy import TrustRouter
from vericlue_ml.voice.nes2net_timeline import VERSION as NES2NET_TIMELINE_VERSION

RETRY_HINTS = frozenset(get_args(RetryHint))
DEFAULT_HINT = "MORE_LIGHT"


class SessionFlow:
    def _manual_demo_complete(self, session: Session) -> bool:
        policy = self.settings.manual_demo_policy
        if (
            policy is None
            or session.purpose != "onboarding"
            or session.account_id
            or session.manual_demo_policy_id != policy.policy_id
            or not session.id_confirmed
            or session.id_edited
            or session.id_source not in {"server_qr", "ocr"}
            or not session.id_front
        ):
            return False
        manual_modules = (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH)
        for module in (
            Module.QUALITY,
            *self.router.profile.presence_modules,
            Module.GAZE_TRACKING,
            Module.HEAD_TURN,
            *manual_modules,
        ):
            measured = session.results.get(module)
            if (
                measured is None
                or measured.module != module
                or measured.status != Status.OK
                or measured.gate != Gate.PASS
                or measured.error_code is not None
                or measured.model_version.startswith("mock")
            ):
                return False
            if module in manual_modules and (
                measured.quality.get("manual_demo") is not True
                or measured.quality.get("demo_policy_id") != policy.policy_id
                or not measured.model_version.endswith(policy.version_suffix)
            ):
                return False
        match = session.results[Module.FACE_MATCH]
        return (
            match.quality.get("consistency_verified") is True
            and match.quality.get("views_from_video") is True
        )

    @staticmethod
    def _evaluation_fields(session: Session) -> dict:
        return (
            {
                "evaluation_mode": session.created_model_mode,
                "demo_policy_id": session.manual_demo_policy_id,
            }
            if session.created_model_mode in {"manual_demo", "manual_full_demo"}
            and session.manual_demo_policy_id
            else {}
        )

    def _finalize_response(self, session: Session, **kwargs) -> FinalizeResponse:
        return FinalizeResponse(**self._evaluation_fields(session), **kwargs)

    def _voice_response(self, session: Session, **kwargs) -> VoiceResponse:
        return VoiceResponse(**self._evaluation_fields(session), **kwargs)

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
        orchestrator: object | None = None,
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
        self.orchestrator = orchestrator

    @staticmethod
    def _flow_unavailable() -> ApiError:
        return ApiError(503, "flow_unavailable", "Luồng xác minh này chưa sẵn sàng.")

    def _require_fitted_calibrator(self, module: Module, version: str) -> None:
        try:
            artifact = self.router.calibrators.load(module, version)
        except CalibrationError as exc:
            raise self._flow_unavailable() from exc
        if not isinstance(artifact, Calibrator) or artifact.provisional:
            raise self._flow_unavailable()

    def _require_match_threshold(
        self, path_str: str | None, expected_versions: tuple[str, ...]
    ) -> None:
        if not path_str:
            raise self._flow_unavailable()
        try:
            artifact = MatchThreshold.model_validate_json(
                Path(path_str).read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise self._flow_unavailable() from exc
        if artifact.model_version not in expected_versions:
            raise self._flow_unavailable()

    def _ensure_standard_flow_ready(
        self,
        purpose: str,
        *,
        account_bound: bool,
        session: Session | None = None,
        voice_step: bool = False,
    ) -> None:
        """Fail closed unless every real model, calibration artifact, consent and account prerequisite is ready."""
        s = self.settings
        needs_voice = (
            purpose in {"onboarding", "recovery"}
            or voice_step
            or (session is not None and session.voice_requested)
        )
        if (
            s.use_mock_models is not False
            or s.manual_face_demo
            or s.manual_full_demo
            or not s.require_privacy_consent
            or not s.session_face_models
            or (needs_voice and not s.session_voice_models)
            or not s.identity_face_from_video
            or self.orchestrator is None
        ):
            raise self._flow_unavailable()
        if session is not None and session.created_model_mode != "real":
            raise self._flow_unavailable()
        enrolled_flow = account_bound or (purpose == "onboarding" and s.account_enrollment)
        if enrolled_flow:
            try:
                self.accounts._master()
            except ApiError as exc:
                raise self._flow_unavailable() from exc
            if (
                not s.require_media_proof
                or len(s.id_hmac_key.get_secret_value().encode("utf-8")) < 32
            ):
                raise self._flow_unavailable()
        if purpose in {"onboarding", "recovery"} and (
            not s.session_face_checks
            or (purpose == "onboarding" and not s.identity_card_enabled)
            or not s.identity_consistency_required
            or not s.identity_voice_continuity
        ):
            raise self._flow_unavailable()

        required_modules = [
            *self.router.profile.finalize_modules,
            Module.FACE_MATCH,
        ]
        if needs_voice:
            required_modules.extend(self.router.profile.voice_step_modules)
        if purpose in {"onboarding", "recovery"}:
            required_modules.extend(
                (Module.GAZE_TRACKING, Module.HEAD_TURN, Module.FACE_CONTINUITY)
            )
            if enrolled_flow and Module.LIPSYNC not in required_modules:
                required_modules.append(Module.LIPSYNC)

        failed = set(getattr(self.orchestrator, "failed_modules", ()))
        detectors: dict[Module, object] = {}
        for module in dict.fromkeys(required_modules):
            if str(module) in failed or module.value in failed:
                raise self._flow_unavailable()
            detector = self.orchestrator.loaded_detector(module)
            if detector is None:
                raise self._flow_unavailable()
            version = str(getattr(detector, "version", "") or "")
            if not version or "mock" in version.lower() or version == "unavailable":
                raise self._flow_unavailable()
            detectors[module] = detector

        protocol = (
            session.challenge.dynamic.version
            if session is not None and session.challenge.dynamic is not None
            else 2
        )
        for attack_mod in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
            det = detectors[attack_mod]
            backend = getattr(det, "backend", None)
            if backend is None or getattr(det, "manual_demo", None) is not None:
                raise self._flow_unavailable()
            if purpose == "reauth":
                base_ver = str(getattr(backend, "version", "") or "")
                expected_attack_ver = (
                    base_ver if attack_mod == Module.FACE_PAD else f"{base_ver}+single-frame-v1"
                )
            else:
                frames_ver = str(getattr(backend, "frames_version", "") or "")
                expected_attack_ver = session_model_version(frames_ver, protocol)
            self._require_fitted_calibrator(attack_mod, expected_attack_ver)

        if needs_voice:
            spoof_ver = str(getattr(detectors[Module.VOICE_SPOOF], "version", "") or "")
            # VOICE-08/VOICE-13: NES2Net timeline remains diagnostic-only until parity & calib_fit exist.
            if spoof_ver == NES2NET_TIMELINE_VERSION:
                raise self._flow_unavailable()
            self._require_fitted_calibrator(Module.VOICE_SPOOF, spoof_ver)

            if (
                Module.LIPSYNC in self.router.profile.voice_modules
                or purpose == "recovery"
                or (purpose == "onboarding" and s.account_enrollment)
            ):
                lipsync_ver = str(getattr(detectors[Module.LIPSYNC], "version", "") or "")
                self._require_fitted_calibrator(Module.LIPSYNC, lipsync_ver)

        if purpose == "onboarding":
            self._require_match_threshold(
                s.identity_face_calibration,
                (VIDEO_MATCH_VERSION, VIDEO_MATCH_VERSION + "+head12s-v2"),
            )
            self._require_match_threshold(
                s.identity_consistency_calibration,
                (
                    VIDEO_MATCH_VERSION + "+view-consistency-v1",
                    VIDEO_MATCH_VERSION + "+head12s-v2+view-consistency-v1",
                ),
            )
            self._require_match_threshold(s.identity_voice_calibration, (FACE_VOICE_VERSION,))
        elif purpose == "reauth":
            if not account_bound:
                raise self._flow_unavailable()
            self._require_match_threshold(s.identity_account_calibration, (REAUTH_MATCH_VERSION,))
        elif purpose == "recovery":
            if not account_bound:
                raise self._flow_unavailable()
            self._require_match_threshold(
                s.identity_recovery_calibration, (RECOVERY_MATCH_VERSION,)
            )
            self._require_match_threshold(
                s.identity_consistency_calibration,
                (
                    VIDEO_MATCH_VERSION + "+view-consistency-v1",
                    VIDEO_MATCH_VERSION + "+head12s-v2+view-consistency-v1",
                ),
            )
            self._require_match_threshold(s.identity_voice_calibration, (FACE_VOICE_VERSION,))
        else:
            raise self._flow_unavailable()

        if session is not None:
            endpoint = "voice" if session.voice_requested else "finalize"
            try:
                require_categories(self.sessions.db, s, session, endpoint)
            except ApiError as exc:
                raise self._flow_unavailable() from exc
            if purpose == "recovery" and account_bound:
                identity = self.account_auth.current(session)
                if (
                    not session.otp_verified
                    or not session.phone_hmac
                    or session.phone_hmac != self.accounts.phone_hmac(identity.receipt.account_id)
                    or not session.media_public_key_spki
                ):
                    raise self._flow_unavailable()
            elif purpose == "onboarding" and s.account_enrollment:
                if not session.otp_verified or not session.phone_hmac:
                    raise self._flow_unavailable()

    # --- tạo phiên -------------------------------------------------------
    def create(
        self, scenario: str, request: CreateSessionRequest | None = None
    ) -> CreateSessionResponse:
        policy = self.settings.manual_demo_policy
        if self.settings.manual_face_demo and (
            request is None or request.purpose != "onboarding" or request.account_id
        ):
            raise ApiError(
                503, "flow_unavailable", "Bản trình diễn này chỉ hỗ trợ đăng ký thử nghiệm."
            )
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
            self._ensure_standard_flow_ready(request.purpose, account_bound=False)
        session = self.sessions.create(
            scenario=scenario,
            challenge=generate_challenge(self.settings),
            ttl_seconds=self.settings.session_ttl_seconds,
            signer=self.settings.session_token_signer,
        )
        session.created_model_mode = (
            "manual_demo"
            if self.settings.manual_face_demo
            else "manual_full_demo"
            if self.settings.manual_full_demo
            else "mock"
            if self.settings.use_mock_models is True
            else "real"
            if self.settings.use_mock_models is False
            else "mixed"
        )
        if policy is not None:
            session.manual_demo_policy_id = policy.policy_id
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
            **self._evaluation_fields(session),
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
        self._ensure_evaluation_binding(session)
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

    def _ensure_evaluation_binding(self, session: Session) -> None:
        policy = self.settings.manual_demo_policy
        expected = policy.policy_id if policy is not None else None
        expected_manual_mode = (
            "manual_demo"
            if self.settings.manual_face_demo
            else "manual_full_demo"
            if self.settings.manual_full_demo
            else None
        )
        if session.manual_demo_policy_id != expected:
            raise ApiError(
                409, "session_expired", "Cấu hình trình diễn đã đổi. Vui lòng bắt đầu phiên mới."
            )
        if (
            session.created_model_mode in {"manual_demo", "manual_full_demo"}
            or expected_manual_mode is not None
        ) and session.created_model_mode != expected_manual_mode:
            raise ApiError(
                409, "session_expired", "Cấu hình trình diễn đã đổi. Vui lòng bắt đầu phiên mới."
            )

    def ensure_flow_available(self, session: Session) -> None:
        """A saved mock session must not become usable after switching the server to real."""
        self._ensure_evaluation_binding(session)
        if session.account_id:
            if session.purpose == "reauth":
                self.account_auth.require_verified(session)
            else:
                self.account_auth.current(session)
            if self.settings.manual_full_demo:
                return
            self._ensure_standard_flow_ready(
                session.purpose or "", account_bound=True, session=session
            )
            return
        if session.purpose is not None and self.settings.use_mock_models is not True:
            self._ensure_standard_flow_ready(session.purpose, account_bound=False, session=session)

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
        outcome = (
            Outcome(
                "review",
                reason="manual demo only",
                config_version="manual-face-demo-v1-" + s.manual_demo_policy.policy_id[:16],
                thresholds={
                    "evaluation_mode": "manual_demo",
                    "demo_policy_id": s.manual_demo_policy.policy_id,
                    "manual_thresholds": s.manual_demo_policy.model_dump(),
                    "calibrated": False,
                },
                results=results,
            )
            if s.manual_face_demo
            else self._manual_full_demo_finalize(
                session,
                results,
                session_valid=session_valid and self._valid_time(session, color_challenge=True),
            )
            if s.manual_full_demo
            else self.router.finalize(
                results,
                retries_used=session.retries_used,
                max_retries=s.max_retries,
                session_valid=session_valid and self._valid_time(session, color_challenge=True),
            )
        )
        outcome = route_face(outcome, session.purpose, device_verified=session.device_verified)
        # This bridge compares a newly scanned card. Reauth uses enrolled identity/device
        # context (FLOW-05/SEC-02), not a fresh CCCD or the staff-review card gate.
        if session.account_id or s.identity_card_enabled and session.purpose != "reauth":
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
            if (
                session_valid
                and self._valid_time(session, color_challenge=True)
                and session.retries_used < min(s.max_retries, 1)
                and self._pose_capture_retryable(session, outcome)
            ):
                outcome = replace(
                    outcome, status="retry", retry_hint="HOLD_STILL", reason="capture pose quality"
                )
            elif not motion_ok and outcome.status in {"pass", "voice_challenge"}:
                outcome = replace(outcome, status="review", reason="motion checks incomplete")
        session.results.update(outcome.results)
        demo_complete = bool(
            s.manual_face_demo
            and session_valid
            and self._valid_time(session, color_challenge=True)
            and self._manual_demo_complete(session)
        )
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
            return self._finalize_response(
                session,
                status="retry",
                retry_hint=hint,  # type: ignore[arg-type]
                attempts_left=s.max_retries - session.retries_used,
                challenge=session.challenge,
            )
        if status == "voice_challenge":
            session.voice_requested = True
            session.voice_owed = True
            session.voice_rereads_used = 0  # yêu cầu đọc câu mới
            return self._finalize_response(
                session,
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
        return self._finalize_response(session, status=status, demo_complete=demo_complete)

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
        outcome = (
            self._manual_full_demo_voice(
                session,
                results,
                session_valid=session_valid and self._valid_time(session, voice_challenge=True),
            )
            if self.settings.manual_full_demo
            else self.router.voice(
                results,
                rereads_used=session.voice_rereads_used,
                session_valid=session_valid and self._valid_time(session, voice_challenge=True),
            )
        )
        outcome = route_voice(outcome, session.purpose)
        if session.purpose == "recovery" or (
            session.purpose == "onboarding" and self.settings.account_enrollment
        ):
            outcome = self._lipsync_gate(session, outcome)
        if (
            session.account_id
            or self.settings.identity_card_enabled
            and session.purpose != "reauth"
        ):
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
            return self._voice_response(
                session,
                status="voice_challenge",
                voice_prompt=self._new_prompt(session),
                attempts_left=MAX_VOICE_REREADS - session.voice_rereads_used,
                voice_challenge_id=session.voice_challenge_id,
            )
        session.voice_requested = False  # kết thúc bước giọng nói
        session.completed = True
        if outcome.status == "review":
            self._open_case(session, outcome)
            return self._voice_response(session, status="review")
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
        return self._voice_response(
            session,
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

    def _pose_capture_retryable(self, session: Session, outcome) -> bool:
        """One fresh capture for measured pose quality; never clear errors or attack gates."""
        head = session.results.get(Module.HEAD_TURN)
        if (
            outcome.status not in {"pass", "voice_challenge", "review"}
            or outcome.priority != "normal"
            or outcome.status == "review"
            and outcome.reason
            not in {
                "face missing/error/degraded/probability",
                "manual demo only",
                "face attack gate not passed",
            }
            or head is None
            or head.module != Module.HEAD_TURN
            or head.status != Status.DEGRADED
            or head.gate != Gate.UNCLEAR
            or head.error_code is not None
            or [e.value for e in head.evidence if e.name == "head_reason"] != ["pose_out_of_range"]
        ):
            return False
        for module in (Module.QUALITY, Module.GAZE_TRACKING, *self.router.profile.presence_modules):
            measured = session.results.get(module)
            if (
                measured is None
                or measured.module != module
                or measured.status != Status.OK
                or measured.gate != Gate.PASS
                or measured.error_code is not None
            ):
                return False
        for module in (Module.FACE_PAD, Module.FACE_DEEPFAKE, Module.FACE_MATCH):
            # Preserve router calibration failures rather than using raw OK model output.
            measured = outcome.results.get(module, session.results.get(module))
            if measured is None:
                if module == Module.FACE_MATCH and not (
                    session.account_id or self.settings.identity_card_enabled
                ):
                    continue
                return False
            if measured.module != module or measured.gate == Gate.FAIL:
                return False
            if measured.status == Status.OK and measured.error_code is None:
                if module in (Module.FACE_PAD, Module.FACE_DEEPFAKE) and (
                    measured.prob_attack is None
                    or measured.prob_attack >= self.router.config.face.a
                ):
                    return False
                if module == Module.FACE_MATCH and measured.gate != Gate.PASS:
                    return False
                continue
            if not (
                measured.status == Status.DEGRADED
                and measured.gate == Gate.UNCLEAR
                and measured.error_code == ErrorCode.E_LOW_QUALITY
            ):
                return False
        return True

    def _manual_full_demo_finalize(
        self, session: Session, results: dict[Module, object], *, session_valid: bool
    ) -> Outcome:
        policy = self.settings.manual_demo_policy
        base = {
            "config_version": "manual-full-demo-v1-" + (policy.policy_id[:16] if policy else "0"),
            "thresholds": {
                "evaluation_mode": "manual_full_demo",
                "demo_policy_id": policy.policy_id if policy else None,
                "manual_thresholds": policy.model_dump() if policy else {},
                "calibrated": False,
            },
            "results": results,
        }
        if (
            not session_valid
            or policy is None
            or session.manual_demo_policy_id != policy.policy_id
            or session.created_model_mode != "manual_full_demo"
        ):
            return Outcome("review", priority="high", reason="invalid session", **base)
        quality = results.get(Module.QUALITY)
        if quality is None or quality.status != Status.OK or quality.error_code is not None:
            return Outcome("review", reason="quality missing/error/degraded", **base)
        if quality.gate != Gate.PASS:
            hint = next(
                (
                    e.value
                    for e in quality.evidence
                    if e.name == "retry_hint" and isinstance(e.value, str)
                ),
                "MORE_LIGHT",
            )
            if session.retries_used >= self.settings.max_retries:
                return Outcome("review", reason="quality not passed; retry limit", **base)
            return Outcome("retry", retry_hint=hint, reason="quality not passed", **base)
        for mod in self.router.profile.presence_modules:
            pres = results.get(mod)
            if pres is None or pres.status != Status.OK or pres.error_code is not None:
                return Outcome("review", reason="presence missing/error/degraded", **base)
            if pres.gate == Gate.FAIL:
                return Outcome("review", priority="high", reason="presence failed", **base)
            if pres.gate == Gate.UNCLEAR:
                if session.retries_used >= self.settings.max_retries:
                    return Outcome("review", reason="presence unclear; retry limit", **base)
                return Outcome(
                    "retry", retry_hint="BRIGHTNESS_UP", reason="presence unclear", **base
                )
        for mod in (Module.FACE_PAD, Module.FACE_DEEPFAKE):
            attack = results.get(mod)
            if (
                attack is None
                or attack.status != Status.OK
                or attack.error_code is not None
                or attack.gate != Gate.PASS
                or "mock" in attack.model_version.lower()
                or attack.quality.get("manual_demo") is not True
                or attack.quality.get("demo_policy_id") != policy.policy_id
                or not attack.model_version.endswith(policy.version_suffix)
            ):
                return Outcome("review", reason="face attack gate not passed", **base)
        return Outcome("pass", reason="manual full demo pass", **base)

    def _manual_full_demo_voice(
        self, session: Session, results: dict[Module, object], *, session_valid: bool
    ) -> Outcome:
        policy = self.settings.manual_demo_policy
        decision_results = dict(results)
        lipsync_required = (
            session.purpose == "recovery"
            or (session.purpose == "onboarding" and self.settings.account_enrollment)
            or Module.LIPSYNC in self.router.profile.required_voice_step_modules
        )
        if not lipsync_required:
            for mod in self.router.profile.advisory_voice_modules:
                res = decision_results.get(mod)
                if res is not None and not any(
                    ev.name == "decision_role" and ev.value == "advisory" for ev in res.evidence
                ):
                    role = Evidence(
                        type="text",
                        name="decision_role",
                        value="advisory",
                        label_vi="Khớp môi chỉ tham khảo ở chế độ MVP",
                    )
                    decision_results[mod] = res.model_copy(
                        update={"evidence": [*res.evidence, role]}
                    )
        base = {
            "config_version": "manual-full-demo-v1-" + (policy.policy_id[:16] if policy else "0"),
            "thresholds": {
                "evaluation_mode": "manual_full_demo",
                "demo_policy_id": policy.policy_id if policy else None,
                "manual_thresholds": policy.model_dump() if policy else {},
                "calibrated": False,
            },
            "results": decision_results,
        }
        if (
            not session_valid
            or policy is None
            or session.manual_demo_policy_id != policy.policy_id
            or session.created_model_mode != "manual_full_demo"
        ):
            return Outcome("review", priority="high", reason="invalid session", **base)
        challenge = decision_results.get(Module.VOICE_CHALLENGE)
        if (
            challenge is None
            or challenge.status != Status.OK
            or challenge.error_code is not None
            or "mock" in challenge.model_version.lower()
        ):
            return Outcome("review", reason="voice challenge missing/error/degraded", **base)
        if challenge.gate == Gate.FAIL:
            action = (
                "voice_challenge" if session.voice_rereads_used < MAX_VOICE_REREADS else "review"
            )
            return Outcome(action, reason="phrase mismatch", **base)
        if challenge.gate != Gate.PASS:
            return Outcome("review", reason="phrase unclear", **base)
        flags = [
            e.value
            for r in decision_results.values()
            for e in r.evidence
            if e.name == "splice_flags"
        ]
        invalid_flag = False
        positive_flag = False
        for value in flags:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (isinstance(value, float) and not math.isfinite(value))
            ):
                invalid_flag = True
            elif value > 0:
                positive_flag = True
        if positive_flag:
            return Outcome("review", priority="high", reason="positive splice flag", **base)
        if invalid_flag:
            return Outcome("review", reason="invalid splice flag", **base)
        spoof = decision_results.get(Module.VOICE_SPOOF)
        if not policy.accepts_voice_spoof(spoof):
            return Outcome("review", reason="voice spoof not passed", **base)
        if lipsync_required:
            lipsync = decision_results.get(Module.LIPSYNC)
            if (
                lipsync is None
                or lipsync.module != Module.LIPSYNC
                or lipsync.status != Status.OK
                or lipsync.error_code is not None
                or lipsync.gate != Gate.PASS
                or "mock" in lipsync.model_version.lower()
            ):
                return Outcome("review", reason="lipsync not passed", **base)
        return Outcome("pass", reason="manual full demo voice pass", **base)

    def _lipsync_gate(self, session: Session, outcome):
        """Recovery and voiced account enrollment require verified lipsync (never advisory)."""
        lipsync = session.results.get(Module.LIPSYNC)
        if (
            lipsync is not None
            and not self.settings.manual_full_demo
            and self.settings.use_mock_models is False
            and lipsync.module == Module.LIPSYNC
            and lipsync.status == Status.OK
            and lipsync.error_code is None
            and "mock" not in lipsync.model_version.lower()
        ):
            if lipsync.prob_attack is None and lipsync.score is not None:
                try:
                    artifact = self.router.calibrators.load(Module.LIPSYNC, lipsync.model_version)
                    if isinstance(artifact, Calibrator) and not artifact.provisional:
                        prob = float(artifact.predict([lipsync.score])[0])
                        lipsync = lipsync.model_copy(update={"prob_attack": prob})
                except CalibrationError:
                    pass
            if lipsync.gate in {None, Gate.PASS} and lipsync.prob_attack is not None:
                gate = (
                    Gate.PASS
                    if 0 <= lipsync.prob_attack <= self.router.config.voice.spoof_threshold
                    else Gate.FAIL
                )
                lipsync = lipsync.model_copy(update={"gate": gate})
            session.results[Module.LIPSYNC] = lipsync
            if Module.LIPSYNC in outcome.results:
                outcome = replace(outcome, results={**outcome.results, Module.LIPSYNC: lipsync})
        require_real_gate = (
            self.settings.manual_full_demo
            or self.settings.use_mock_models is False
            or (lipsync is not None and lipsync.gate is not None)
        )
        allowed = (
            lipsync is not None
            and lipsync.module == Module.LIPSYNC
            and lipsync.status == Status.OK
            and lipsync.error_code is None
            and (
                (
                    lipsync.gate == Gate.PASS
                    and (
                        not (
                            self.settings.manual_full_demo or self.settings.use_mock_models is False
                        )
                        or "mock" not in lipsync.model_version.lower()
                    )
                )
                if require_real_gate
                else (
                    lipsync.prob_attack is not None
                    and 0 <= lipsync.prob_attack <= self.router.config.voice.spoof_threshold
                )
            )
        )
        if lipsync is not None and any(e.name == "decision_role" for e in lipsync.evidence):
            cleaned = lipsync.model_copy(
                update={"evidence": [e for e in lipsync.evidence if e.name != "decision_role"]}
            )
            session.results[Module.LIPSYNC] = cleaned
            if Module.LIPSYNC in outcome.results:
                outcome = replace(outcome, results={**outcome.results, Module.LIPSYNC: cleaned})
        if not allowed and outcome.status == "pass":
            return replace(outcome, status="review", reason="lipsync not passed")
        return outcome

    def _identity_gate(self, session: Session, outcome):
        """A face match is one required signal, never an override of PAD or voice failures."""
        match = session.results.get(Module.FACE_MATCH)
        thresholds = dict(outcome.thresholds)
        policy = self.settings.manual_demo_policy
        manual = self.settings.manual_face_demo or self.settings.manual_full_demo
        suffix = policy.version_suffix if manual and policy is not None else ""
        base_versions = (
            (RECOVERY_MATCH_VERSION if session.purpose == "recovery" else REAUTH_MATCH_VERSION,)
            if session.account_id
            else (VIDEO_MATCH_VERSION, VIDEO_MATCH_VERSION + "+head12s-v2")
            if self.settings.identity_face_from_video
            else (MATCH_VERSION,)
        )
        expected_versions = tuple(v + suffix for v in base_versions) if manual else base_versions
        if match is not None and match.model_version in expected_versions:
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
            and match.model_version in expected_versions
            and match.status == Status.OK
            and match.error_code is None
            and match.gate == Gate.PASS
            and (
                (
                    policy is not None
                    and session.manual_demo_policy_id == policy.policy_id
                    and match.quality.get("manual_demo") is True
                    and match.quality.get("demo_policy_id") == policy.policy_id
                )
                if manual
                else match.quality.get("manual_demo") is not True
            )
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

    def _continuity_gate(self, session: Session, outcome):
        result = session.results.get(Module.FACE_CONTINUITY)
        reference = session.results.get(Module.FACE_MATCH)
        policy = self.settings.manual_demo_policy
        manual = self.settings.manual_full_demo and policy is not None
        suffix = policy.version_suffix if manual else ""
        expected_version = FACE_VOICE_VERSION + suffix
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
            and result.model_version == expected_version
            and result.status == Status.OK
            and result.error_code is None
            and result.gate == Gate.PASS
            and (
                (
                    session.manual_demo_policy_id == policy.policy_id
                    and result.quality.get("manual_demo") is True
                    and result.quality.get("demo_policy_id") == policy.policy_id
                )
                if manual
                else result.quality.get("manual_demo") is not True
            )
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
