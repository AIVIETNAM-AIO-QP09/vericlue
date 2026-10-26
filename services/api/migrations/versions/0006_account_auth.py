"""SEC-02 durable L0 claims and atomic device replacement receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0006_account_auth"
down_revision = "0005_accounts"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_proof_uses",
        sa.Column("session_id", sa.String(80), primary_key=True),
        sa.Column("message_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "account_recoveries",
        sa.Column("session_id", sa.String(80), primary_key=True),
        sa.Column("account_id", sa.String(80), nullable=False),
        sa.Column("previous_device_id", sa.String(80), nullable=False, unique=True),
        sa.Column("device_id", sa.String(80), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_recoveries_account_id", "account_recoveries", ["account_id"])


def downgrade() -> None:
    op.drop_table("account_recoveries")
    op.drop_table("device_proof_uses")
