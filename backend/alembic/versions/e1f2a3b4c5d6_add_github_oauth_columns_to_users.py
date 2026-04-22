"""add_github_oauth_columns_to_users

Revision ID: e1f2a3b4c5d6
Revises: fcdd7f228503
Create Date: 2026-04-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "fcdd7f228503"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("github_access_token_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("github_token_iv", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("github_login", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "github_login")
    op.drop_column("users", "github_token_iv")
    op.drop_column("users", "github_access_token_enc")
