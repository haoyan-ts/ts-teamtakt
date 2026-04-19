"""Replace AbsenceType StrEnum with FK-backed absence_types table

Revision ID: e2f4a6b8c0d1
Revises: b1c4e7f2a935
Create Date: 2026-04-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f4a6b8c0d1"
down_revision: Union[str, Sequence[str], None] = "b1c4e7f2a935"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed UUIDs must match ABSENCE_TYPE_UUIDS in app/db/models/absence.py
_ABSENCE_TYPES = [
    ("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "holiday"),
    ("b2c3d4e5-f6a7-8901-bcde-f12345678901", "exchanged_holiday"),
    ("c3d4e5f6-a7b8-9012-cdef-123456789012", "illness"),
    ("d4e5f6a7-b8c9-0123-defa-234567890123", "other"),
]

# Map old enum string → new UUID (for backfill)
_ENUM_TO_UUID = {name: uid for uid, name in _ABSENCE_TYPES}


def upgrade() -> None:
    # 1. Create the new absence_types table
    op.create_table(
        "absence_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Seed the 4 default rows with fixed UUIDs
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

    # 3. Add absence_type_id column as nullable first (for backfill)
    op.add_column(
        "absences",
        sa.Column("absence_type_id", sa.Uuid(), nullable=True),
    )

    # 4. Backfill: map old string values to fixed UUIDs
    conn = op.get_bind()
    for enum_val, uuid_val in _ENUM_TO_UUID.items():
        conn.execute(
            sa.text(
                "UPDATE absences SET absence_type_id = :uid"
                " WHERE absence_type = :val"
            ),
            {"uid": uuid_val, "val": enum_val},
        )

    # 5. Make absence_type_id NOT NULL
    op.alter_column("absences", "absence_type_id", nullable=False)

    # 6. Add FK constraint
    op.create_foreign_key(
        "fk_absences_absence_type_id",
        "absences",
        "absence_types",
        ["absence_type_id"],
        ["id"],
    )

    # 7. Drop the old string column
    #    (native_enum=False used VARCHAR — no PG enum type to drop)
    op.drop_column("absences", "absence_type")


def downgrade() -> None:
    # 1. Add the old string column back (nullable first)
    op.add_column(
        "absences",
        sa.Column("absence_type", sa.String(), nullable=True),
    )

    # 2. Backfill: map UUIDs back to string values
    conn = op.get_bind()
    for uuid_val, enum_val in _ABSENCE_TYPES:
        conn.execute(
            sa.text(
                "UPDATE absences SET absence_type = :val"
                " WHERE absence_type_id = :uid"
            ),
            {"val": enum_val, "uid": uuid_val},
        )

    # 3. Make absence_type NOT NULL
    op.alter_column("absences", "absence_type", nullable=False)

    # 4. Drop FK constraint and absence_type_id column
    op.drop_constraint("fk_absences_absence_type_id", "absences", type_="foreignkey")
    op.drop_column("absences", "absence_type_id")

    # 5. Drop the absence_types table
    op.drop_table("absence_types")
