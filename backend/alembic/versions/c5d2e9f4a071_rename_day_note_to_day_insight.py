"""Rename daily_records.day_note to day_insight

Revision ID: c5d2e9f4a071
Revises: a4c9d2e7f831
Create Date: 2026-04-20 00:00:00.000000

Changes:
  - daily_records.day_note  → daily_records.day_insight  (Text NULL)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d2e9f4a071"
down_revision: Union[str, None] = "a4c9d2e7f831"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("daily_records") as batch_op:
            batch_op.alter_column(
                "day_note",
                new_column_name="day_insight",
                existing_type=sa.Text(),
                existing_nullable=True,
            )
    else:
        op.alter_column(
            "daily_records",
            "day_note",
            new_column_name="day_insight",
            existing_type=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("daily_records") as batch_op:
            batch_op.alter_column(
                "day_insight",
                new_column_name="day_note",
                existing_type=sa.Text(),
                existing_nullable=True,
            )
    else:
        op.alter_column(
            "daily_records",
            "day_insight",
            new_column_name="day_note",
            existing_type=sa.Text(),
            existing_nullable=True,
        )
