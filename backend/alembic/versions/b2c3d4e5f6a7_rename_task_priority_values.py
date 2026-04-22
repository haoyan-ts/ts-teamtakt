"""Rename task priority values to P0-P3 scale

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-22 00:00:00.000000

Change tasks.priority from (low, medium, high) to
(p0_critical, p1_high, p2_medium, p3_low).
No CHECK constraint exists, so only existing row values are migrated.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

_tasks = sa.table("tasks", sa.column("priority", sa.String))

_UPGRADE_MAP = {
    "high": "p1_high",
    "medium": "p2_medium",
    "low": "p3_low",
}

_DOWNGRADE_MAP = {v: k for k, v in _UPGRADE_MAP.items()}
# p0_critical has no previous equivalent — set to NULL on downgrade


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in _UPGRADE_MAP.items():
        conn.execute(
            sa.update(_tasks).where(_tasks.c.priority == old).values(priority=new)
        )


def downgrade() -> None:
    conn = op.get_bind()
    # p0_critical → NULL (no equivalent in old scheme)
    conn.execute(
        sa.update(_tasks)
        .where(_tasks.c.priority == "p0_critical")
        .values(priority=None)
    )
    for old, new in _DOWNGRADE_MAP.items():
        if old == "p0_critical":
            continue
        conn.execute(
            sa.update(_tasks).where(_tasks.c.priority == old).values(priority=new)
        )
