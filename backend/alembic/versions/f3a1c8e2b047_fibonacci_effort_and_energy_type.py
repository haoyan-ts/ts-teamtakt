"""Migrate effort to Fibonacci scale and add energy_type to daily_work_logs

Revision ID: f3a1c8e2b047
Revises: e2f4a6b8c0d1
Create Date: 2026-04-20 00:00:00.000000

Breaking changes:
  - daily_work_logs.effort and tasks.estimated_effort now only allow
    Fibonacci values: 1, 2, 3, 5, 8.  Legacy values are remapped:
      4 → 5
      5 → 8
    (applied as a single CASE expression to avoid double-hop)
  - daily_work_logs gains a nullable energy_type column (VARCHAR).

Downgrade note:
  Reverse remap uses 8 → 5 and 5 → 4. Rows whose original effort was 5
  (remapped to 8) cannot be distinguished from rows originally entered as 8
  (which did not exist under the old 1–5 scale, so in practice all 8s came
  from old 5s).  This is documented and accepted.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a1c8e2b047"
down_revision: Union[str, None] = "e2f4a6b8c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fibonacci values allowed for effort
_FIBONACCI = (1, 2, 3, 5, 8)
_FIBONACCI_CHECK = "effort IN (1, 2, 3, 5, 8)"
_ESTIMATED_EFFORT_CHECK = (
    "estimated_effort IS NULL OR estimated_effort IN (1, 2, 3, 5, 8)"
)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ------------------------------------------------------------------
    # 1. Remap effort values using a single CASE to avoid double-hop.
    #    Old 4 → 5, old 5 → 8.  Any value already in Fibonacci is kept.
    # ------------------------------------------------------------------
    bind.execute(
        sa.text(
            "UPDATE daily_work_logs SET effort = CASE"
            "  WHEN effort = 5 THEN 8"
            "  WHEN effort = 4 THEN 5"
            "  ELSE effort"
            " END"
            " WHERE effort IN (4, 5)"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE tasks SET estimated_effort = CASE"
            "  WHEN estimated_effort = 5 THEN 8"
            "  WHEN estimated_effort = 4 THEN 5"
            "  ELSE estimated_effort"
            " END"
            " WHERE estimated_effort IN (4, 5)"
        )
    )

    # ------------------------------------------------------------------
    # 2. Add CHECK constraints (PostgreSQL only; SQLite ignores ADD CONSTRAINT).
    # ------------------------------------------------------------------
    if dialect == "postgresql":
        op.create_check_constraint(
            "ck_dwl_effort_fibonacci",
            "daily_work_logs",
            _FIBONACCI_CHECK,
        )
        op.create_check_constraint(
            "ck_task_estimated_effort_fibonacci",
            "tasks",
            _ESTIMATED_EFFORT_CHECK,
        )

    # ------------------------------------------------------------------
    # 3. Add nullable energy_type column to daily_work_logs.
    # ------------------------------------------------------------------
    op.add_column(
        "daily_work_logs",
        sa.Column(
            "energy_type",
            sa.String(length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ------------------------------------------------------------------
    # 1. Drop energy_type column.
    # ------------------------------------------------------------------
    op.drop_column("daily_work_logs", "energy_type")

    # ------------------------------------------------------------------
    # 2. Drop CHECK constraints (PostgreSQL only).
    # ------------------------------------------------------------------
    if dialect == "postgresql":
        op.drop_constraint("ck_dwl_effort_fibonacci", "daily_work_logs", type_="check")
        op.drop_constraint("ck_task_estimated_effort_fibonacci", "tasks", type_="check")

    # ------------------------------------------------------------------
    # 3. Reverse remap: 8 → 5, 5 → 4.
    # ------------------------------------------------------------------
    bind.execute(
        sa.text(
            "UPDATE daily_work_logs SET effort = CASE"
            "  WHEN effort = 8 THEN 5"
            "  WHEN effort = 5 THEN 4"
            "  ELSE effort"
            " END"
            " WHERE effort IN (5, 8)"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE tasks SET estimated_effort = CASE"
            "  WHEN estimated_effort = 8 THEN 5"
            "  WHEN estimated_effort = 5 THEN 4"
            "  ELSE estimated_effort"
            " END"
            " WHERE estimated_effort IN (5, 8)"
        )
    )
