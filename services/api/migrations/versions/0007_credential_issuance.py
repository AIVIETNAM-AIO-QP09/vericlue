"""One holder commitment and encrypted idempotent BBS credential per source session."""

import sqlalchemy as sa
from alembic import op

revision = "0007_credential_issuance"
down_revision = "0006_account_auth"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential_issuances",
        sa.Column(
            "session_id", sa.String(80), sa.ForeignKey("sessions.session_id"), primary_key=True
        ),
        sa.Column("offer_sha256", sa.String(64), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("credential_issuances")
