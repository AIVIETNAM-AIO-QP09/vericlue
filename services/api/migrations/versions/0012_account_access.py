"""APP-01 account password/profile access with bounded revocable login sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0012_account_access"
down_revision = "0011_account_template_consent"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_access_credentials",
        sa.Column(
            "account_id", sa.String(80), sa.ForeignKey("accounts.account_id"), primary_key=True
        ),
        sa.Column("username_hmac", sa.String(64), nullable=True, unique=True),
        sa.Column("device_id", sa.String(80), nullable=False),
        sa.Column("setup_session_id", sa.String(80), nullable=False, unique=True),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wrapped_key", sa.Text(), nullable=True),
        sa.Column("encrypted_payload", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_account_access_credentials_expires_at", "account_access_credentials", ["expires_at"]
    )
    op.create_table(
        "account_access_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "account_id", sa.String(80), sa.ForeignKey("accounts.account_id"), nullable=False
        ),
        sa.Column("device_id", sa.String(80), nullable=False),
        sa.Column("authentication_method", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_account_access_tokens_account_id", "account_access_tokens", ["account_id"])
    op.create_index("ix_account_access_tokens_expires_at", "account_access_tokens", ["expires_at"])
    op.create_table(
        "account_access_face_uses",
        sa.Column("session_id", sa.String(80), primary_key=True),
        sa.Column(
            "account_id", sa.String(80), sa.ForeignKey("accounts.account_id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_account_access_face_uses_account_id", "account_access_face_uses", ["account_id"]
    )
    op.create_table(
        "account_access_attempts",
        sa.Column("bucket_hash", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_account_access_attempts_window_started_at",
        "account_access_attempts",
        ["window_started_at"],
    )


def downgrade() -> None:
    for table in (
        "account_access_attempts",
        "account_access_face_uses",
        "account_access_tokens",
        "account_access_credentials",
    ):
        op.drop_table(table)
