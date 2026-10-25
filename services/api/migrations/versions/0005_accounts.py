"""FLOW-05 encrypted demo templates and account device bindings."""

import sqlalchemy as sa
from alembic import op

revision = "0005_accounts"
down_revision = "0004_media_proof"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.String(80), primary_key=True),
        sa.Column("source_session_id", sa.String(80), nullable=False, unique=True),
        sa.Column("id_number_hmac", sa.String(64), nullable=True, unique=True),
        sa.Column("phone_hmac", sa.String(64), nullable=True),
        sa.Column("device_id", sa.String(80), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wrapped_key", sa.Text, nullable=True),
        sa.Column("encrypted_payload", sa.Text, nullable=True),
    )
    op.create_index("ix_accounts_expires_at", "accounts", ["expires_at"])


def downgrade() -> None:
    op.drop_table("accounts")
