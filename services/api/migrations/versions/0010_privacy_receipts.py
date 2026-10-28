"""Bounded append-only consent/withdrawal ledger, independent of erased session DEKs."""

import sqlalchemy as sa
from alembic import op

revision = "0010_privacy_receipts"
down_revision = "0009_credential_key_registry"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "privacy_events",
        sa.Column("receipt_id", sa.String(40), primary_key=True),
        sa.Column(
            "session_id", sa.String(80), sa.ForeignKey("sessions.session_id"), nullable=False
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("categories", sa.JSON, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('consent', 'withdrawal', 'files_erased')", name="ck_privacy_event_kind"
        ),
    )
    op.create_index("ix_privacy_events_session_id", "privacy_events", ["session_id"])
    for suffix, kind in [("withdrawal", "withdrawal"), ("files_erased", "files_erased")]:
        op.create_index(
            "uq_privacy_" + suffix,
            "privacy_events",
            ["session_id"],
            unique=True,
            sqlite_where=sa.text("kind = '" + kind + "'"),
            postgresql_where=sa.text("kind = '" + kind + "'"),
        )
    if op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER privacy_events_no_{action.lower()} BEFORE {action} ON privacy_events BEGIN SELECT RAISE(ABORT, 'privacy_events is append-only'); END"
            )
    else:
        op.execute(
            "CREATE FUNCTION privacy_events_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'privacy_events is append-only'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER privacy_events_immutable BEFORE UPDATE OR DELETE ON privacy_events FOR EACH ROW EXECUTE FUNCTION privacy_events_immutable()"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER privacy_events_immutable ON privacy_events")
        op.execute("DROP FUNCTION privacy_events_immutable()")
    op.drop_table("privacy_events")
