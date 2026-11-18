"""Store immutable revisions for saved designs.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table("design_revisions")
    if not existing:
        op.create_table(
            "design_revisions",
            sa.Column("design_id", sa.Integer(), sa.ForeignKey("designs.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("number", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("snapshot_sha256", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if op.get_context().dialect.name == "sqlite":
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS delete_design_revisions
            AFTER DELETE ON designs
            BEGIN
                DELETE FROM design_revisions WHERE design_id = OLD.id;
            END
        """)


def downgrade() -> None:
    if op.get_context().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS delete_design_revisions")
    op.drop_table("design_revisions")
