"""Add insight to tasks and rename work_note to insight on daily_work_logs

Revision ID: a4c9d2e7f831
Revises: f3a1c8e2b047
Create Date: 2026-04-20 00:00:00.000000

Changes:
  - daily_work_logs.work_note  → daily_work_logs.insight  (VARCHAR(500) NULL)
  - tasks.insight added as VARCHAR(500) NULL
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c9d2e7f831"
down_revision: Union[str, None] = "f3a1c8e2b047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ------------------------------------------------------------------
    # 1. Rename daily_work_logs.work_note → insight
    # ------------------------------------------------------------------
    if dialect == "sqlite":
        # SQLite does not support RENAME COLUMN before 3.25 / alembic batch
        with op.batch_alter_table("daily_work_logs") as batch_op:
            batch_op.alter_column(
                "work_note",
                new_column_name="insight",
                existing_type=sa.Text(),
                existing_nullable=True,
            )
    else:
        op.alter_column(
            "daily_work_logs",
            "work_note",
            new_column_name="insight",
            existing_type=sa.Text(),
            existing_nullable=True,
        )

    # ------------------------------------------------------------------
    # 2. Add tasks.insight  (VARCHAR 500, nullable)
    # ------------------------------------------------------------------
    op.add_column(
        "tasks",
        sa.Column("insight", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Remove tasks.insight
    op.drop_column("tasks", "insight")

    # Rename daily_work_logs.insight → work_note
    if dialect == "sqlite":
        with op.batch_alter_table("daily_work_logs") as batch_op:
            batch_op.alter_column(
                "insight",
                new_column_name="work_note",
                existing_type=sa.Text(),
                existing_nullable=True,
            )
    else:
        op.alter_column(
            "daily_work_logs",
            "insight",
            new_column_name="work_note",
            existing_type=sa.Text(),
            existing_nullable=True,
        )
