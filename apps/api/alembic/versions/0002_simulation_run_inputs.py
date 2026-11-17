"""Store frozen inputs for new simulation runs.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Direct startup and Compose can have already created this additive table.
    existing = not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table("simulation_run_inputs")
    if not existing:
        op.create_table(
            "simulation_run_inputs",
            sa.Column(
                "run_id", sa.Integer(), sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("input_json", sa.Text(), nullable=False),
            sa.Column("input_sha256", sa.String(64), nullable=False),
        )
    if op.get_context().dialect.name == "sqlite":
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS delete_simulation_run_inputs
            AFTER DELETE ON simulation_runs
            BEGIN
                DELETE FROM simulation_run_inputs WHERE run_id = OLD.id;
            END
        """)


def downgrade() -> None:
    if op.get_context().dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS delete_simulation_run_inputs")
    op.drop_table("simulation_run_inputs")
