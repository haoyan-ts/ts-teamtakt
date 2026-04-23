"""merge_github_project_and_oauth_heads

Revision ID: d0b797503987
Revises: b3d1e2f4a896, e1f2a3b4c5d6
Create Date: 2026-04-23 19:24:19.919120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0b797503987'
down_revision: Union[str, Sequence[str], None] = ('b3d1e2f4a896', 'e1f2a3b4c5d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
