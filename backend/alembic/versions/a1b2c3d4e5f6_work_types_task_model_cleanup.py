"""Add work_types, update Task fields, remove category_sub_types

Revision ID: a1b2c3d4e5f6
Revises: f3a1c8e2b047
Create Date: 2026-04-22 00:00:00.000000

Summary of changes:
  - Create work_types table (replaces category_sub_types)
  - Seed work_types: Software, Hardware, Documents, Slide, Other
  - tasks.project_id: drop NOT NULL constraint (make nullable)
  - tasks.work_type_id: add nullable FK → work_types.id
  - tasks.priority: add nullable VARCHAR column (low/medium/high)
  - tasks.due_date: add nullable DATE column
  - tasks.sub_type_id: drop FK + column
  - daily_work_logs.blocker_type_id: drop FK + column
  - Deactivate old category seeds (OKR, Routine, Interrupt)
  - Insert new category seeds
  - Add partial unique index uq_dwl_tag_primary on
    daily_work_log_self_assessment_tags (is_primary=TRUE)
  - Drop category_sub_types table
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "d7e3f9a2b564"
branch_labels = None
depends_on = None

_WORK_TYPE_SEEDS = [
    ("Software", 0),
    ("Hardware", 1),
    ("Documents", 2),
    ("Slide", 3),
    ("Other", 4),
]

_NEW_CATEGORY_SEEDS = [
    ("Development", 0),
    ("Testing & QA", 1),
    ("Planning", 2),
    ("Documentation", 3),
    ("Support", 4),
    ("Research", 5),
    ("Other", 6),
]

_OLD_CATEGORY_SEEDS = ["OKR", "Routine", "Interrupt"]


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Create work_types table
    # ------------------------------------------------------------------
    op.create_table(
        "work_types",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False),
    )

    # ------------------------------------------------------------------
    # 2. Seed work_types
    # ------------------------------------------------------------------
    wt_table = sa.table(
        "work_types",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        wt_table,
        [
            {"id": uuid.uuid4(), "name": name, "is_active": True, "sort_order": order}
            for name, order in _WORK_TYPE_SEEDS
        ],
    )

    # ------------------------------------------------------------------
    # 3. tasks: make project_id nullable
    # ------------------------------------------------------------------
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("project_id", existing_type=sa.Uuid(as_uuid=True), nullable=True)

    # ------------------------------------------------------------------
    # 4. tasks: add work_type_id, priority, due_date
    # ------------------------------------------------------------------
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("work_type_id", sa.Uuid(as_uuid=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("priority", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(sa.Column("due_date", sa.Date, nullable=True))
        batch_op.create_foreign_key(
            "tasks_work_type_id_fkey",
            "work_types",
            ["work_type_id"],
            ["id"],
        )

    # ------------------------------------------------------------------
    # 5. tasks: drop sub_type_id
    # ------------------------------------------------------------------
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("tasks_sub_type_id_fkey", type_="foreignkey")
        batch_op.drop_column("sub_type_id")

    # ------------------------------------------------------------------
    # 6. daily_work_logs: drop blocker_type_id
    # ------------------------------------------------------------------
    with op.batch_alter_table("daily_work_logs") as batch_op:
        batch_op.drop_constraint(
            "daily_work_logs_blocker_type_id_fkey", type_="foreignkey"
        )
        batch_op.drop_column("blocker_type_id")

    # ------------------------------------------------------------------
    # 7. Deactivate old category seeds
    # ------------------------------------------------------------------
    categories_t = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    conn.execute(
        sa.update(categories_t)
        .where(categories_t.c.name.in_(_OLD_CATEGORY_SEEDS))
        .values(is_active=False)
    )

    # ------------------------------------------------------------------
    # 8. Insert new category seeds (skip if already present)
    # ------------------------------------------------------------------
    cat_table = sa.table(
        "categories",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    for name, order in _NEW_CATEGORY_SEEDS:
        exists = conn.execute(
            sa.select(sa.text("1")).select_from(
                sa.table("categories", sa.column("name", sa.String))
            ).where(sa.column("name") == name)
        ).scalar()
        if not exists:
            op.bulk_insert(
                cat_table,
                [{"id": uuid.uuid4(), "name": name, "is_active": True, "sort_order": order}],
            )

    # ------------------------------------------------------------------
    # 9. Add partial unique index for is_primary on junction table
    # ------------------------------------------------------------------
    with op.batch_alter_table("daily_work_log_self_assessment_tags") as batch_op:
        batch_op.create_index(
            "uq_dwl_tag_primary",
            ["daily_work_log_id"],
            unique=True,
            postgresql_where=sa.text("is_primary = TRUE"),
            sqlite_where=sa.text("is_primary = 1"),
        )

    # ------------------------------------------------------------------
    # 10. Drop category_sub_types table
    # ------------------------------------------------------------------
    op.drop_table("category_sub_types")


def downgrade() -> None:
    # Re-create category_sub_types
    op.create_table(
        "category_sub_types",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "category_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False),
    )

    # Remove partial unique index
    with op.batch_alter_table("daily_work_log_self_assessment_tags") as batch_op:
        batch_op.drop_index("uq_dwl_tag_primary")

    # Restore daily_work_logs.blocker_type_id
    with op.batch_alter_table("daily_work_logs") as batch_op:
        batch_op.add_column(
            sa.Column("blocker_type_id", sa.Uuid(as_uuid=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "daily_work_logs_blocker_type_id_fkey",
            "blocker_types",
            ["blocker_type_id"],
            ["id"],
        )

    # Restore tasks.sub_type_id; remove new columns
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_work_type_id", type_="foreignkey")
        batch_op.drop_column("due_date")
        batch_op.drop_column("priority")
        batch_op.drop_column("work_type_id")
        batch_op.add_column(
            sa.Column("sub_type_id", sa.Uuid(as_uuid=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "tasks_sub_type_id_fkey",
            "category_sub_types",
            ["sub_type_id"],
            ["id"],
        )
        batch_op.alter_column("project_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)

    op.drop_table("work_types")
