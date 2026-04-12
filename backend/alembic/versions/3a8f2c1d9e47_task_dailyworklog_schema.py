"""replace task_entries with tasks and daily_work_logs

Revision ID: 3a8f2c1d9e47
Revises: 94f7455afcb9
Create Date: 2026-04-12 09:00:00.000000

Each unique carry-over chain in task_entries (identified by its root row where
carried_from_id IS NULL) becomes exactly one Task row.  Every entry in the chain
(including the root) becomes one DailyWorkLog row linked to that Task.

Downgrade note: carry-over chains (carried_from_id) cannot be reconstructed from
Task rows.  All restored task_entry rows will have carried_from_id = NULL.
"""

from typing import Sequence, Union
import uuid as uuid_module

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "3a8f2c1d9e47"
down_revision: Union[str, Sequence[str], None] = "94f7455afcb9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: introduce tasks + daily_work_logs, remove task_entries."""

    # ── 1. tasks ──────────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("sub_type_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "todo",
                "running",
                "done",
                "blocked",
                name="task_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("estimated_effort", sa.Integer(), nullable=True),
        sa.Column("blocker_type_id", sa.Uuid(), nullable=True),
        sa.Column("github_issue_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.Date(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["blocker_type_id"], ["blocker_types.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["sub_type_id"], ["category_sub_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Partial unique index: same GitHub issue cannot be linked twice per user
    op.create_index(
        "uq_task_github_issue_url",
        "tasks",
        ["assignee_id", "github_issue_url"],
        unique=True,
        postgresql_where=sa.text("github_issue_url IS NOT NULL"),
    )

    # ── 2. daily_work_logs ────────────────────────────────────────────────────
    op.create_table(
        "daily_work_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("daily_record_id", sa.Uuid(), nullable=False),
        sa.Column("effort", sa.Integer(), nullable=False),
        sa.Column("work_note", sa.Text(), nullable=True),
        sa.Column("blocker_type_id", sa.Uuid(), nullable=True),
        sa.Column("blocker_text", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["blocker_type_id"], ["blocker_types.id"]),
        sa.ForeignKeyConstraint(["daily_record_id"], ["daily_records.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "daily_record_id", name="uq_dwl_task_record"),
    )

    # ── 3. daily_work_log_self_assessment_tags ────────────────────────────────
    op.create_table(
        "daily_work_log_self_assessment_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_work_log_id", sa.Uuid(), nullable=False),
        sa.Column("self_assessment_tag_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["daily_work_log_id"], ["daily_work_logs.id"]),
        sa.ForeignKeyConstraint(
            ["self_assessment_tag_id"], ["self_assessment_tags.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "daily_work_log_id", "self_assessment_tag_id", name="uq_dwl_tag"
        ),
    )

    # ── 4. projects.github_repo ───────────────────────────────────────────────
    op.add_column("projects", sa.Column("github_repo", sa.Text(), nullable=True))

    # ── 5. Data migration ─────────────────────────────────────────────────────
    _migrate_task_entries_up(op.get_bind())

    # ── 6. Drop old tables ────────────────────────────────────────────────────
    op.drop_table("task_entry_self_assessment_tags")
    op.drop_table("task_entries")


def downgrade() -> None:
    """Downgrade schema: restore task_entries, remove tasks + daily_work_logs.

    carry-over chains (carried_from_id) cannot be reconstructed from Task rows.
    All restored task_entry rows will have carried_from_id = NULL.
    """

    # ── 1. Recreate task_entries (exact DDL from migration 94f7455afcb9) ──────
    op.create_table(
        "task_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_record_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("sub_type_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("effort", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "todo",
                "running",
                "done",
                "blocked",
                name="task_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("blocker_type_id", sa.Uuid(), nullable=True),
        sa.Column("blocker_text", sa.Text(), nullable=True),
        sa.Column("carried_from_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["blocker_type_id"], ["blocker_types.id"]),
        sa.ForeignKeyConstraint(["carried_from_id"], ["task_entries.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["daily_record_id"], ["daily_records.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["sub_type_id"], ["category_sub_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 2. Recreate task_entry_self_assessment_tags (exact DDL from 94f7455afcb9)
    op.create_table(
        "task_entry_self_assessment_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_entry_id", sa.Uuid(), nullable=False),
        sa.Column("self_assessment_tag_id", sa.Uuid(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["self_assessment_tag_id"], ["self_assessment_tags.id"]
        ),
        sa.ForeignKeyConstraint(["task_entry_id"], ["task_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_entry_id", "self_assessment_tag_id", name="uq_task_entry_tag"
        ),
    )

    # ── 3. Data migration ─────────────────────────────────────────────────────
    _migrate_task_entries_down(op.get_bind())

    # ── 4. Drop new tables ────────────────────────────────────────────────────
    op.drop_table("daily_work_log_self_assessment_tags")
    op.drop_table("daily_work_logs")
    op.drop_index("uq_task_github_issue_url", table_name="tasks")
    op.drop_table("tasks")

    # ── 5. Remove github_repo from projects ───────────────────────────────────
    op.drop_column("projects", "github_repo")


# ── Data migration helpers ─────────────────────────────────────────────────────


def _migrate_task_entries_up(conn) -> None:
    """Convert task_entries carry-over chains into Task + DailyWorkLog rows.

    Algorithm:
    1. For every chain root (carried_from_id IS NULL): create one Task row.
       Task metadata (category, project, status, …) comes from the root entry.
       assignee_id / created_by are taken from the root entry's DailyRecord owner.
    2. For every entry (roots and their descendants via the recursive CTE):
       create one DailyWorkLog row linked to the Task for that chain.
    3. Migrate self-assessment tags from task_entry_self_assessment_tags.
    """

    # ── Step A: one Task per chain root ───────────────────────────────────────
    roots = conn.execute(
        text(
            """
        SELECT
            te.id,
            te.category_id,
            te.sub_type_id,
            te.project_id,
            te.task_description,
            te.status,
            te.blocker_type_id,
            dr.user_id,
            dr.created_at
        FROM task_entries te
        JOIN daily_records dr ON dr.id = te.daily_record_id
        WHERE te.carried_from_id IS NULL
    """
        )
    ).fetchall()

    # root_entry_id (str) -> new task UUID (str)
    root_to_task: dict[str, str] = {}

    for root in roots:
        task_id = str(uuid_module.uuid4())
        root_to_task[str(root.id)] = task_id
        conn.execute(
            text(
                """
            INSERT INTO tasks (
                id, title, description, assignee_id, created_by, project_id,
                category_id, sub_type_id, status, estimated_effort,
                blocker_type_id, github_issue_url, created_at, closed_at, is_active
            ) VALUES (
                :id, :title, NULL, :assignee_id, :created_by, :project_id,
                :category_id, :sub_type_id, :status, NULL,
                :blocker_type_id, NULL, :created_at, NULL, TRUE
            )
        """
            ),
            {
                "id": task_id,
                "title": root.task_description,
                "assignee_id": str(root.user_id),
                "created_by": str(root.user_id),
                "project_id": str(root.project_id),
                "category_id": str(root.category_id),
                "sub_type_id": (
                    str(root.sub_type_id) if root.sub_type_id is not None else None
                ),
                "status": root.status,
                "blocker_type_id": (
                    str(root.blocker_type_id)
                    if root.blocker_type_id is not None
                    else None
                ),
                "created_at": root.created_at,
            },
        )

    if not root_to_task:
        return  # nothing to migrate

    # ── Step B: one DailyWorkLog per entry (all chain members) ───────────────
    chain_rows = conn.execute(
        text(
            """
        WITH RECURSIVE chain AS (
            SELECT id AS entry_id, id AS root_id
            FROM task_entries
            WHERE carried_from_id IS NULL
            UNION ALL
            SELECT te.id, c.root_id
            FROM task_entries te
            JOIN chain c ON te.carried_from_id = c.entry_id
        )
        SELECT
            chain.entry_id,
            chain.root_id,
            te.daily_record_id,
            te.effort,
            te.blocker_type_id,
            te.blocker_text,
            te.sort_order
        FROM chain
        JOIN task_entries te ON te.id = chain.entry_id
    """
        )
    ).fetchall()

    # entry_id (str) -> new daily_work_log UUID (str)
    entry_to_dwl: dict[str, str] = {}

    for row in chain_rows:
        task_id = root_to_task.get(str(row.root_id))
        if task_id is None:
            # Orphaned entry with no reachable root — skip gracefully
            continue
        dwl_id = str(uuid_module.uuid4())
        entry_to_dwl[str(row.entry_id)] = dwl_id
        conn.execute(
            text(
                """
            INSERT INTO daily_work_logs (
                id, task_id, daily_record_id, effort, work_note,
                blocker_type_id, blocker_text, sort_order
            ) VALUES (
                :id, :task_id, :daily_record_id, :effort, NULL,
                :blocker_type_id, :blocker_text, :sort_order
            )
        """
            ),
            {
                "id": dwl_id,
                "task_id": task_id,
                "daily_record_id": str(row.daily_record_id),
                "effort": row.effort,
                "blocker_type_id": (
                    str(row.blocker_type_id)
                    if row.blocker_type_id is not None
                    else None
                ),
                "blocker_text": row.blocker_text,
                "sort_order": row.sort_order,
            },
        )

    # ── Step C: self-assessment tags ──────────────────────────────────────────
    tag_rows = conn.execute(
        text(
            """
        SELECT id, task_entry_id, self_assessment_tag_id, is_primary
        FROM task_entry_self_assessment_tags
    """
        )
    ).fetchall()

    for tag in tag_rows:
        dwl_id = entry_to_dwl.get(str(tag.task_entry_id))
        if dwl_id is None:
            continue
        conn.execute(
            text(
                """
            INSERT INTO daily_work_log_self_assessment_tags (
                id, daily_work_log_id, self_assessment_tag_id, is_primary
            ) VALUES (
                :id, :daily_work_log_id, :self_assessment_tag_id, :is_primary
            )
        """
            ),
            {
                "id": str(uuid_module.uuid4()),
                "daily_work_log_id": dwl_id,
                "self_assessment_tag_id": str(tag.self_assessment_tag_id),
                "is_primary": tag.is_primary,
            },
        )


def _migrate_task_entries_down(conn) -> None:
    """Restore daily_work_logs back to task_entries (best-effort).

    carried_from_id chains cannot be reconstructed; all restored rows get
    carried_from_id = NULL.  Task metadata (category, project, status) is
    sourced from the parent Task row.
    """

    # ── Step A: one task_entry per daily_work_log ─────────────────────────────
    dwl_rows = conn.execute(
        text(
            """
        SELECT
            dwl.id,
            dwl.daily_record_id,
            dwl.effort,
            dwl.blocker_type_id,
            dwl.blocker_text,
            dwl.sort_order,
            t.title,
            t.category_id,
            t.sub_type_id,
            t.project_id,
            t.status
        FROM daily_work_logs dwl
        JOIN tasks t ON t.id = dwl.task_id
    """
        )
    ).fetchall()

    # daily_work_log_id (str) -> new task_entry UUID (str)
    dwl_to_entry: dict[str, str] = {}

    for row in dwl_rows:
        entry_id = str(uuid_module.uuid4())
        dwl_to_entry[str(row.id)] = entry_id
        conn.execute(
            text(
                """
            INSERT INTO task_entries (
                id, daily_record_id, category_id, sub_type_id,
                project_id, task_description, effort, status,
                blocker_type_id, blocker_text, carried_from_id, sort_order
            ) VALUES (
                :id, :daily_record_id, :category_id, :sub_type_id,
                :project_id, :task_description, :effort, :status,
                :blocker_type_id, :blocker_text, NULL, :sort_order
            )
        """
            ),
            {
                "id": entry_id,
                "daily_record_id": str(row.daily_record_id),
                "category_id": str(row.category_id),
                "sub_type_id": (
                    str(row.sub_type_id) if row.sub_type_id is not None else None
                ),
                "project_id": str(row.project_id),
                "task_description": row.title,
                "effort": row.effort,
                "status": row.status,
                "blocker_type_id": (
                    str(row.blocker_type_id)
                    if row.blocker_type_id is not None
                    else None
                ),
                "blocker_text": row.blocker_text,
                "sort_order": row.sort_order,
            },
        )

    # ── Step B: self-assessment tags ──────────────────────────────────────────
    tag_rows = conn.execute(
        text(
            """
        SELECT id, daily_work_log_id, self_assessment_tag_id, is_primary
        FROM daily_work_log_self_assessment_tags
    """
        )
    ).fetchall()

    for tag in tag_rows:
        entry_id = dwl_to_entry.get(str(tag.daily_work_log_id))
        if entry_id is None:
            continue
        conn.execute(
            text(
                """
            INSERT INTO task_entry_self_assessment_tags (
                id, task_entry_id, self_assessment_tag_id, is_primary
            ) VALUES (
                :id, :task_entry_id, :self_assessment_tag_id, :is_primary
            )
        """
            ),
            {
                "id": str(uuid_module.uuid4()),
                "task_entry_id": entry_id,
                "self_assessment_tag_id": str(tag.self_assessment_tag_id),
                "is_primary": tag.is_primary,
            },
        )
