import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AdminSettings(Base):
    __tablename__ = "admin_settings"
    __table_args__ = (
        UniqueConstraint("key", "team_id", name="uq_admin_settings_key_team"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    # Per-team MS Teams channel configuration (key="ms_teams_config")
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    teams_channel_id: Mapped[str | None] = mapped_column(String, nullable=True)
    teams_team_id: Mapped[str | None] = mapped_column(String, nullable=True)
