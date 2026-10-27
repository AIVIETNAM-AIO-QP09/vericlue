"""SQLAlchemy records; media bytes stay on volumes, never in database rows."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default="incomplete")
    ever_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    media_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class SessionKeyRow(Base):
    __tablename__ = "session_keys"
    session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    wrapped_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountRow(Base):
    __tablename__ = "accounts"
    account_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_session_id: Mapped[str] = mapped_column(String(80), unique=True)
    # Nullable after expiration: live identities are unique; tombstones retain no lookup PII.
    id_number_hmac: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    phone_hmac: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wrapped_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_payload: Mapped[str | None] = mapped_column(Text, nullable=True)


class MediaProofUseRow(Base):
    __tablename__ = "media_proof_uses"
    nonce_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(80), index=True)
    attempt_id: Mapped[str] = mapped_column(String(80))
    stage: Mapped[str] = mapped_column(String(10))
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    key_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeviceProofUseRow(Base):
    __tablename__ = "device_proof_uses"
    session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    message_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CredentialIssuanceRow(Base):
    __tablename__ = "credential_issuances"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), primary_key=True)
    offer_sha256: Mapped[str] = mapped_column(String(64))
    key_id: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)


class AccountRecoveryRow(Base):
    __tablename__ = "account_recoveries"
    session_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(80), index=True)
    previous_device_id: Mapped[str] = mapped_column(String(80), unique=True)
    device_id: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccessEventRow(Base):
    __tablename__ = "access_events"
    __table_args__ = (Index("uq_access_events_scope_prev", "scope", "prev_hash", unique=True),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(100), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(40))
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)


class ModuleResultRow(Base):
    __tablename__ = "module_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), index=True)
    module: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prob_attack: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DecisionRow(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    thresholds: Mapped[dict] = mapped_column(JSON, default=dict)
    config_version: Mapped[str] = mapped_column(String(80), default="provisional@PLAT-04")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewCaseRow(Base):
    __tablename__ = "review_cases"
    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), unique=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(30), default="open")
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    initial_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    final_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ReviewEventRow(Base):
    __tablename__ = "review_events"
    # Chuỗi băm không rẽ nhánh ở tầng DB (migration 0002); sự kiện đầu dùng hash genesis.
    __table_args__ = (
        Index("uq_review_events_case_prev_hash", "case_id", "prev_hash", unique=True),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.case_id"), index=True)
    actor: Mapped[str] = mapped_column(String(100), default="staff-unverified")
    action: Mapped[str] = mapped_column(String(40))
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ForensicJobRow(Base):
    __tablename__ = "forensic_jobs"
    job_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    file_sha256: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(30), default="done")
    verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    media_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ForensicSegmentRow(Base):
    __tablename__ = "forensic_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("forensic_jobs.job_id"), index=True)
    t_start: Mapped[float] = mapped_column(Float)
    t_end: Mapped[float] = mapped_column(Float)
    signals: Mapped[list] = mapped_column(JSON, default=list)


class CleanupAuditRow(Base):
    __tablename__ = "cleanup_audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    files: Mapped[list] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(String(80), default="media_cleanup")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
