"""SEC-09 append-only account template consent ledger and account receipt link."""

import sqlalchemy as sa
from alembic import op

revision = "0011_account_template_consent"
down_revision = "0010_privacy_receipts"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_template_consents",
        sa.Column("receipt_id", sa.String(40), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(80),
            sa.ForeignKey("sessions.session_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("retention_seconds", sa.Integer, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose = 'account_template'", name="ck_account_template_purpose"),
        sa.CheckConstraint("retention_seconds = 86400", name="ck_account_template_retention"),
    )
    op.create_index(
        "ix_account_template_consents_session_id",
        "account_template_consents",
        ["session_id"],
        unique=True,
    )
    op.add_column("accounts", sa.Column("consent_receipt_id", sa.String(40), nullable=True))
    if op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER account_template_consents_no_{action.lower()} BEFORE {action} ON account_template_consents BEGIN SELECT RAISE(ABORT, 'account_template_consents is append-only'); END"
            )
    else:
        op.create_foreign_key(
            "fk_accounts_consent_receipt_id",
            "accounts",
            "account_template_consents",
            ["consent_receipt_id"],
            ["receipt_id"],
        )
        op.execute(
            "CREATE FUNCTION account_template_consents_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'account_template_consents is append-only'; END; $$"
        )
        op.execute(
            "CREATE TRIGGER account_template_consents_immutable BEFORE UPDATE OR DELETE ON account_template_consents FOR EACH ROW EXECUTE FUNCTION account_template_consents_immutable()"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("fk_accounts_consent_receipt_id", "accounts", type_="foreignkey")
        op.execute("DROP TRIGGER account_template_consents_immutable ON account_template_consents")
        op.execute("DROP FUNCTION account_template_consents_immutable()")
    else:
        op.execute("DROP TRIGGER account_template_consents_no_update")
        op.execute("DROP TRIGGER account_template_consents_no_delete")
    op.drop_column("accounts", "consent_receipt_id")
    op.drop_table("account_template_consents")
