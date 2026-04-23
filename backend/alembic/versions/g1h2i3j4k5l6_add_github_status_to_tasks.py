"""add_github_status_to_tasks

Revision ID: g1h2i3j4k5l6
Revises: fcdd7f228503
Create Date: 2026-04-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, None] = "d0b797503987"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("github_status", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "github_status")
