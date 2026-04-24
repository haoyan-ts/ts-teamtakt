"""Widen Fibonacci effort CHECK constraints to {1,2,3,5,8,13,21}

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-04-24 00:00:00.000000

Changes:
  - Drop old CHECK constraints on daily_work_logs.effort and
    tasks.estimated_effort that allowed only {1, 2, 3, 5, 8}.
  - Add new CHECK constraints allowing the extended Fibonacci set
    {1, 2, 3, 5, 8, 13, 21} for planning-poker / Story Points alignment.
  - Existing data (values 1–8) remains fully valid; no data migration needed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_FIBONACCI_CHECK = "effort IN (1, 2, 3, 5, 8)"
_OLD_ESTIMATED_EFFORT_CHECK = (
    "estimated_effort IS NULL OR estimated_effort IN (1, 2, 3, 5, 8)"
)

_NEW_FIBONACCI_CHECK = "effort IN (1, 2, 3, 5, 8, 13, 21)"
_NEW_ESTIMATED_EFFORT_CHECK = (
    "estimated_effort IS NULL OR estimated_effort IN (1, 2, 3, 5, 8, 13, 21)"
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.drop_constraint(
            "ck_dwl_effort_fibonacci",
            "daily_work_logs",
            type_="check",
        )
        op.drop_constraint(
            "ck_task_estimated_effort_fibonacci",
            "tasks",
            type_="check",
        )
        op.create_check_constraint(
            "ck_dwl_effort_fibonacci",
            "daily_work_logs",
            _NEW_FIBONACCI_CHECK,
        )
        op.create_check_constraint(
            "ck_task_estimated_effort_fibonacci",
            "tasks",
            _NEW_ESTIMATED_EFFORT_CHECK,
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.drop_constraint(
            "ck_dwl_effort_fibonacci",
            "daily_work_logs",
            type_="check",
        )
        op.drop_constraint(
            "ck_task_estimated_effort_fibonacci",
            "tasks",
            type_="check",
        )
        op.create_check_constraint(
            "ck_dwl_effort_fibonacci",
            "daily_work_logs",
            _OLD_FIBONACCI_CHECK,
        )
        op.create_check_constraint(
            "ck_task_estimated_effort_fibonacci",
            "tasks",
            _OLD_ESTIMATED_EFFORT_CHECK,
        )
