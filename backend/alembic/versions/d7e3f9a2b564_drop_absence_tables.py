"""Drop absence_types and absences tables

Revision ID: d7e3f9a2b564
Revises: c5d2e9f4a071
Create Date: 2026-04-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e3f9a2b564"
down_revision: Union[str, Sequence[str], None] = "c5d2e9f4a071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed UUIDs and names from the previous e2f4a6b8c0d1 migration — used for downgrade.
_ABSENCE_TYPES = [
    ("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "holiday"),
    ("b2c3d4e5-f6a7-8901-bcde-f12345678901", "exchanged_holiday"),
    ("c3d4e5f6-a7b8-9012-cdef-123456789012", "illness"),
    ("d4e5f6a7-b8c9-0123-defa-234567890123", "other"),
]


def upgrade() -> None:
    # Drop absences first (FK to absence_types), then absence_types.
    op.drop_table("absences")
    op.drop_table("absence_types")


def downgrade() -> None:
    # Recreate absence_types
    op.create_table(
        "absence_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    absence_types_table = sa.table(
        "absence_types",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        absence_types_table,
        [{"id": uid, "name": name, "is_active": True} for uid, name in _ABSENCE_TYPES],
    )

    # Recreate absences (with absence_type_id FK)
    op.create_table(
        "absences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("absence_type_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["absence_type_id"],
            ["absence_types.id"],
            name="fk_absences_absence_type_id",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "record_date", name="uq_absence_user_date"),
    )
