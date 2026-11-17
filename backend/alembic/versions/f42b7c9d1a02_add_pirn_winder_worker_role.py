"""add_pirn_winder_worker_role

Revision ID: f42b7c9d1a02
Revises: e16c9a3c63cb
Create Date: 2026-11-17 22:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "f42b7c9d1a02"
down_revision = "e16c9a3c63cb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weavers", schema=None, recreate="always") as batch_op:
        batch_op.drop_constraint("ck_weaver_role_type", type_="check")
        batch_op.create_check_constraint(
            "ck_weaver_role_type",
            "role_type IN ('WEAVER', 'PIRN_WINDER', 'HELPER', 'FITTER')",
        )


def downgrade() -> None:
    with op.batch_alter_table("weavers", schema=None, recreate="always") as batch_op:
        batch_op.drop_constraint("ck_weaver_role_type", type_="check")
        batch_op.create_check_constraint(
            "ck_weaver_role_type",
            "role_type IN ('WEAVER', 'HELPER', 'FITTER')",
        )
