"""SEC-02 durable one-use nullifiers for session-bound media signatures."""

import sqlalchemy as sa
from alembic import op

revision = "0004_media_proof"
down_revision = "0003_session_privacy"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_proof_uses",
        sa.Column("nonce_hash", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(80), nullable=False),
        sa.Column("attempt_id", sa.String(80), nullable=False),
        sa.Column("stage", sa.String(10), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("key_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_media_proof_uses_session_id", "media_proof_uses", ["session_id"])


def downgrade() -> None:
    op.drop_table("media_proof_uses")
