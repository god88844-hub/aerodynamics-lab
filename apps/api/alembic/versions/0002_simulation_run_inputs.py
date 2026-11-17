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
    if not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table("simulation_run_inputs"):
        return
    op.create_table(
        "simulation_run_inputs",
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("simulation_runs.id"), primary_key=True),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("simulation_run_inputs")
