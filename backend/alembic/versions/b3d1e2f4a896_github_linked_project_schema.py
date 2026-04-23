"""github_linked_project_schema

Revision ID: b3d1e2f4a896
Revises: fcdd7f228503
Create Date: 2026-04-23 00:00:00.000000

Drops scope/team_id/github_repo from projects and replaces them with
GitHub Project identity columns (github_project_node_id, github_project_number,
github_project_owner).  The projects table (and its FK-dependent tasks rows)
are wiped first — wipe strategy agreed in issue #75.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d1e2f4a896"
down_revision: str | Sequence[str] | None = "fcdd7f228503"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Wipe dependent rows first so FK constraints don't block column drops.
    op.execute("TRUNCATE TABLE tasks RESTART IDENTITY CASCADE")
    op.execute("TRUNCATE TABLE projects RESTART IDENTITY CASCADE")

    # Drop old columns (drop FK constraint on team_id explicitly first).
    op.drop_constraint("projects_team_id_fkey", "projects", type_="foreignkey")
    op.drop_column("projects", "scope")
    op.drop_column("projects", "team_id")
    op.drop_column("projects", "github_repo")

    # Add new GitHub-identity columns.
    op.add_column(
        "projects",
        sa.Column("github_project_node_id", sa.String(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_projects_github_project_node_id",
        "projects",
        ["github_project_node_id"],
    )
    op.add_column(
        "projects",
        sa.Column("github_project_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("github_project_owner", sa.String(), nullable=True),
    )


def downgrade() -> None:
    # The wipe strategy makes a true downgrade impossible.
    raise NotImplementedError(
        "Downgrade not supported: data was wiped during upgrade (issue #75)."
    )
