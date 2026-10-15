"""Kho phiên theo transaction; domain snapshot được ghi tường minh vào DB."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from vericlue_api.db.models import DecisionRow, ModuleResultRow, SessionRow, utcnow
from vericlue_api.schemas.session import Challenge
from vericlue_ml.common.result import Module, ModuleResult


@dataclass
class Session:
    session_id: str
    token: str
    token_expires_at: datetime
    scenario: str
    challenge: Challenge
    images: list[Path] = field(default_factory=list)
    video: Path | None = None
    audio: Path | None = None
    signals: dict = field(default_factory=dict)
    results: dict[Module, ModuleResult] = field(default_factory=dict)
    retries_used: int = 0
    voice_rereads_used: int = 0
    voice_prompt: str | None = None
    voice_requested: bool = False  # finalize đã trả voice_challenge
    case_id: str | None = None


class SessionStore:
    def __init__(self, db: DBSession) -> None:
        self.db = db
        self._loaded: dict[str, tuple[Session, SessionRow]] = {}

    def create(self, *, scenario: str, challenge: Challenge, ttl_seconds: int) -> Session:
        session = Session(
            session_id=f"ses_{secrets.token_hex(8)}",
            token=secrets.token_urlsafe(24),  # TẠM — PLAT-06 thay bằng HMAC + TTL
            token_expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            scenario=scenario,
            challenge=challenge,
        )
        row = SessionRow(session_id=session.session_id, payload=jsonable_encoder(session))
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
        if row is None or not row.payload.get("token"):
            return None
        data = dict(row.payload)
        data["token_expires_at"] = datetime.fromisoformat(data["token_expires_at"])
        data["challenge"] = Challenge.model_validate(data["challenge"])
        data["images"] = [Path(p) for p in data["images"]]
        for key in ("video", "audio"):
            data[key] = Path(data[key]) if data[key] else None
        data["results"] = {
            Module(k): ModuleResult.model_validate(v) for k, v in data["results"].items()
        }
        session = Session(**data)
        self._loaded[session_id] = (session, row)
        return session

    def save_all(self) -> None:
        for session, row in self._loaded.values():
            row.payload = jsonable_encoder(session)
            row.last_activity_at = utcnow()
            row.media_deleted_at = None

    def record_decision(self, session: Session, action: str, *, b: float, a: float) -> None:
        row = self._loaded[session.session_id][1]
        row.status = action if action in {"pass", "review"} else "incomplete"
        row.ever_review = row.ever_review or action == "review"
        # Review retention starts only when staff close the case, not at routing time.
        row.decided_at = utcnow() if action == "pass" else None
        self.db.add(
            DecisionRow(session_id=session.session_id, action=action, thresholds={"b": b, "a": a})
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
