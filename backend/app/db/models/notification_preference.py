import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from . import Base

TRIGGER_TYPES = [
    "missing_day",
    "edit_window_closing",
    "blocker_aging",
    "team_member_blocked",
    "weekly_report_ready",
    "quarterly_draft_ready",
    "team_join_request",
]

# Default channel settings per trigger: (email, teams)
TRIGGER_DEFAULTS: dict[str, tuple[bool, bool]] = {
    "missing_day": (False, True),
    "edit_window_closing": (True, False),
    "blocker_aging": (False, False),
    "team_member_blocked": (False, True),
    "weekly_report_ready": (True, False),
    "quarterly_draft_ready": (True, False),
    "team_join_request": (False, True),
}


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "trigger_type", name="uq_notif_pref_user_trigger"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trigger_type: Mapped[str] = mapped_column(String, nullable=False)
    channel_email: Mapped[bool] = mapped_column(Boolean, nullable=False)
    channel_teams: Mapped[bool] = mapped_column(Boolean, nullable=False)


class HolidayCalendar(Base):
    __tablename__ = "holiday_calendar"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    date: Mapped[Date] = mapped_column(Date, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, default="admin", nullable=False)
    # is_workday=True for exchanged workdays (an otherwise-weekend that becomes a work day)
    is_workday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
