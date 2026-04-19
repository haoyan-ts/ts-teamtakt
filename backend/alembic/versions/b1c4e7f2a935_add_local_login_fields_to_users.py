"""add local login fields to users

Revision ID: b1c4e7f2a935
Revises: 3a8f2c1d9e47
Create Date: 2026-04-19 00:00:00.000000

Adds two columns to the users table to support the narrow bootstrap/recovery
local login feature:
  - password_hash: nullable TEXT to store bcrypt hash (NULL for SSO-only users)
  - allow_local_login: BOOLEAN NOT NULL DEFAULT false (only the seeded admin has true)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4e7f2a935"
down_revision: Union[str, Sequence[str], None] = "3a8f2c1d9e47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "allow_local_login",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "allow_local_login")
    op.drop_column("users", "password_hash")
