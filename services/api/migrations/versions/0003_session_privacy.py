"""SEC-01 session key lifecycle and append-only access audit, no biometric bytes in DB."""

import sqlalchemy as sa
from alembic import op

revision = "0003_session_privacy"
down_revision = "0002_review_chain_unique"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_keys",
        sa.Column("session_id", sa.String(80), primary_key=True),
        sa.Column("wrapped_key", sa.Text, nullable=True),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "access_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_index("ix_access_events_scope", "access_events", ["scope"])
    op.create_index(
        "uq_access_events_scope_prev", "access_events", ["scope", "prev_hash"], unique=True
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION reject_access_event_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'access_events is append-only'; END $$""")
        op.execute("""CREATE TRIGGER access_events_append_only BEFORE UPDATE OR DELETE
            ON access_events FOR EACH ROW EXECUTE FUNCTION reject_access_event_mutation()""")
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER access_events_no_{action.lower()} BEFORE {action}
                ON access_events BEGIN SELECT RAISE(ABORT, 'access_events is append-only'); END""")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER access_events_append_only ON access_events")
        op.execute("DROP FUNCTION reject_access_event_mutation()")
    else:
        op.execute("DROP TRIGGER access_events_no_update")
        op.execute("DROP TRIGGER access_events_no_delete")
    op.drop_table("access_events")
    op.drop_table("session_keys")
