"""Trusted public issuer keys, lifecycle state and operator transition history."""

import sqlalchemy as sa
from alembic import op

revision = "0009_credential_key_registry"
down_revision = "0008_credential_challenges"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential_trust_keys",
        sa.Column("key_id", sa.String(64), primary_key=True),
        sa.Column("issuer", sa.String(200), nullable=False),
        sa.Column("public_key", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("verify_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('staged', 'active', 'verify_only', 'revoked')",
            name="ck_credential_key_state",
        ),
        sa.CheckConstraint(
            "(state = 'verify_only' AND verify_until IS NOT NULL) OR (state <> 'verify_only' AND verify_until IS NULL)",
            name="ck_credential_verify_deadline",
        ),
    )
    op.create_index("ix_credential_trust_keys_issuer", "credential_trust_keys", ["issuer"])
    op.create_index(
        "uq_credential_active_issuer",
        "credential_trust_keys",
        ["issuer"],
        unique=True,
        sqlite_where=sa.text("state = 'active'"),
        postgresql_where=sa.text("state = 'active'"),
    )
    op.create_table(
        "credential_key_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "key_id", sa.String(64), sa.ForeignKey("credential_trust_keys.key_id"), nullable=False
        ),
        sa.Column("from_state", sa.String(16), nullable=True),
        sa.Column("to_state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credential_key_events_key_id", "credential_key_events", ["key_id"])


def downgrade() -> None:
    op.drop_table("credential_key_events")
    op.drop_table("credential_trust_keys")
