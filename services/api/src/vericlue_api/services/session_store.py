"""Kho phiên theo transaction; domain snapshot được ghi tường minh vào DB."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from vericlue_api.core.session_tokens import SessionTokenSigner, token_digest
from vericlue_api.db.models import DecisionRow, ModuleResultRow, SessionRow, utcnow
from vericlue_api.schemas.session import Challenge, SessionPurpose
from vericlue_ml.common.result import Module, ModuleResult


@dataclass
class Session:
    session_id: str
    token_expires_at: datetime
    scenario: str
    challenge: Challenge
    token_hash: str = ""
    token: str = field(default="", repr=False)  # Only present while issuing a new session.
    accepted_steps: list[str] = field(default_factory=list)
    completed: bool = False
    voice_expires_at: datetime | None = None
    images: list[Path] = field(default_factory=list)
    video: Path | None = None
    audio: Path | None = None
    signals: dict = field(default_factory=dict)
    results: dict[Module, ModuleResult] = field(default_factory=dict)
    retries_used: int = 0
    voice_rereads_used: int = 0
    voice_prompt: str | None = None
    voice_requested: bool = False  # finalize đã trả voice_challenge
    # Đã bị đòi đọc câu trong phiên: giữ qua mọi lượt mặt mới cho tới khi xong bước giọng.
    voice_owed: bool = False
    # Lượt mặt hiện tại đã được chấm mà chưa tính vào retries_used (finalize không trả retry).
    face_scored: bool = False
    case_id: str | None = None
    created_at: datetime | None = None  # None: phiên cũ, trước khi có giới hạn tổng
    # Giai đoạn A (FLOW-02, FLOW-03). Không lưu số điện thoại hay số CCCD dạng rõ.
    otp_hash: str | None = None
    otp_expires_at: datetime | None = None
    otp_attempts_left: int = 0
    otp_verified: bool = False
    otp_sends: int = 0
    phone_hmac: str | None = None
    id_front: Path | None = None
    id_back: Path | None = None
    id_fields: dict | None = None
    id_number_hmac: str | None = None
    id_edited: list[str] = field(default_factory=list)  # trường người dùng sửa khác QR
    purpose: SessionPurpose | None = None
    nonce: str | None = None
    reference_image_id: str | None = None
    device_verified: bool = False  # Never populated from request JSON; SEC-02 owns verification.
    voice_challenge_id: str | None = None


class SessionStore:
    def __init__(self, db: DBSession) -> None:
        self.db = db
        self._loaded: dict[str, tuple[Session, SessionRow]] = {}

    @staticmethod
    def _snapshot(session: Session) -> dict:
        return jsonable_encoder(session, exclude={"token"})

    def create(
        self,
        *,
        scenario: str,
        challenge: Challenge,
        ttl_seconds: int,
        signer: SessionTokenSigner,
    ) -> Session:
        session = Session(
            session_id=f"ses_{secrets.token_hex(8)}",
            token_expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            scenario=scenario,
            challenge=challenge,
            created_at=datetime.now(UTC),
        )
        session.token = signer.issue(session.session_id, session.token_expires_at)
        session.token_hash = token_digest(session.token)
        row = SessionRow(session_id=session.session_id, payload=self._snapshot(session))
        self.db.add(row)
        self.db.flush()
        self._loaded[session.session_id] = (session, row)
        return session

    def get(self, session_id: str) -> Session | None:
        if session_id in self._loaded:
            return self._loaded[session_id][0]
        row = self.db.scalar(
            select(SessionRow).where(SessionRow.session_id == session_id).with_for_update()
        )
        # Unsigned legacy credentials are revoked, not silently upgraded.
        if row is None or not row.payload.get("token_hash"):
            return None
        data = dict(row.payload)
        data.pop("token", None)
        data["token_expires_at"] = datetime.fromisoformat(data["token_expires_at"])
        for key in ("created_at", "otp_expires_at", "voice_expires_at"):
            data[key] = datetime.fromisoformat(data[key]) if data.get(key) else None
        data["challenge"] = Challenge.model_validate(data["challenge"])
        data["images"] = [Path(p) for p in data["images"]]
        for key in ("video", "audio", "id_front", "id_back"):
            data[key] = Path(data[key]) if data.get(key) else None
        data["results"] = {
            Module(k): ModuleResult.model_validate(v) for k, v in data["results"].items()
        }
        session = Session(**data)
        self._loaded[session_id] = (session, row)
        return session

    def save_all(self) -> None:
        for session, row in self._loaded.values():
            row.payload = self._snapshot(session)
            row.last_activity_at = utcnow()
            row.media_deleted_at = None

    def record_decision(
        self, session: Session, action: str, *, thresholds: dict, config_version: str
    ) -> None:
        row = self._loaded[session.session_id][1]
        row.status = (
            action if action in {"pass", "review", "deny", "recovery_required"} else "incomplete"
        )
        row.ever_review = row.ever_review or action == "review"
        # Review retention starts only when staff close the case, not at routing time.
        row.decided_at = utcnow() if action in {"pass", "deny", "recovery_required"} else None
        self.db.add(
            DecisionRow(
                session_id=session.session_id,
                action=action,
                thresholds=thresholds,
                config_version=config_version,
            )
        )
        for result in session.results.values():
            payload = result.to_contract()
            self.db.add(
                ModuleResultRow(
                    session_id=session.session_id,
                    module=str(result.module),
                    model_version=result.model_version,
                    status=str(result.status),
                    score=result.score,
                    prob_attack=result.prob_attack,
                    quality=payload.get("quality", {}),
                    evidence=payload.get("evidence", []),
                    payload=payload,
                )
            )
