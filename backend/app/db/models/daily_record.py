import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class DailyRecord(Base):
    __tablename__ = "daily_records"
    __table_args__ = (
        UniqueConstraint("user_id", "record_date", name="uq_daily_record_user_date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_load: Mapped[int] = mapped_column(Integer, nullable=False)
    day_insight: Mapped[str] = mapped_column(Text, nullable=True)
    form_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_checked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    teams_message_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    teams_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
