"""add private ai chat history tables

Revision ID: c2e9a1f4b710
Revises: a8d3f21b9c04
Create Date: 2026-11-22 21:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2e9a1f4b710"
down_revision: Union[str, Sequence[str], None] = "a8d3f21b9c04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "ai_chat_threads" not in existing_tables:
        op.create_table(
            "ai_chat_threads",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_chat_threads_user_id", "ai_chat_threads", ["user_id"], unique=False)
        op.create_index("ix_ai_chat_threads_updated_at", "ai_chat_threads", ["updated_at"], unique=False)

    if "ai_chat_messages" not in existing_tables:
        op.create_table(
            "ai_chat_messages",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("thread_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("has_image", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("model_used", sa.String(length=60), nullable=True),
            sa.Column("tools_used_json", sa.Text(), nullable=True),
            sa.Column("actions_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_chat_msg_role"),
            sa.ForeignKeyConstraint(["thread_id"], ["ai_chat_threads.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_chat_messages_thread_id", "ai_chat_messages", ["thread_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    if "ai_chat_messages" in existing_tables:
        op.drop_table("ai_chat_messages")
    if "ai_chat_threads" in existing_tables:
        op.drop_table("ai_chat_threads")
