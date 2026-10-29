"""Durable verifier challenges; no credentials, proofs or holder identifiers stored."""

import sqlalchemy as sa
from alembic import op

revision = "0008_credential_challenges"
down_revision = "0007_credential_issuance"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential_challenges",
        sa.Column("challenge_id", sa.String(22), primary_key=True),
        sa.Column("audience", sa.String(200), nullable=False),
        sa.Column("issuer", sa.String(200), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(43), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credential_challenges_audience", "credential_challenges", ["audience"])
    op.create_index("ix_credential_challenges_expires_at", "credential_challenges", ["expires_at"])


def downgrade() -> None:
    op.drop_table("credential_challenges")
