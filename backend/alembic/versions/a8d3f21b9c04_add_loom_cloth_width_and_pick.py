"""add_loom_cloth_width_and_pick

Revision ID: a8d3f21b9c04
Revises: f42b7c9d1a02
Create Date: 2026-11-22 21:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "a8d3f21b9c04"
down_revision = "f42b7c9d1a02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("looms")}
    with op.batch_alter_table("looms", schema=None) as batch_op:
        if "cloth_width_in" not in existing_cols:
            batch_op.add_column(sa.Column("cloth_width_in", sa.Numeric(6, 2), nullable=True))
        if "default_pick" not in existing_cols:
            batch_op.add_column(sa.Column("default_pick", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("looms", schema=None) as batch_op:
        batch_op.drop_column("default_pick")
        batch_op.drop_column("cloth_width_in")
