"""Kho phiên trong bộ nhớ (TẠM — PLAT-05 thay bằng PostgreSQL)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, *, scenario: str, challenge: Challenge, ttl_seconds: int) -> Session:
        session = Session(
            session_id=f"ses_{secrets.token_hex(8)}",
            token=secrets.token_urlsafe(24),  # TẠM — PLAT-06 thay bằng HMAC + TTL
            token_expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            scenario=scenario,
            challenge=challenge,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)
