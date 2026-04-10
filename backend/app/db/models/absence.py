import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class AbsenceType(enum.StrEnum):
    holiday = "holiday"
    exchanged_holiday = "exchanged_holiday"
    illness = "illness"
    other = "other"


class Absence(Base):
    __tablename__ = "absences"
    __table_args__ = (
        UniqueConstraint("user_id", "record_date", name="uq_absence_user_date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    absence_type: Mapped[AbsenceType] = mapped_column(
        SAEnum(AbsenceType, name="absence_type", native_enum=False), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UnlockGrant(Base):
    __tablename__ = "unlock_grants"
    __table_args__ = (
        # App-level uniqueness check enforces only one active grant per (user, date).
        # For PostgreSQL, a partial unique index (WHERE revoked_at IS NULL) should
        # be added via Alembic migration.
        UniqueConstraint(
            "user_id",
            "record_date",
            name="uq_unlock_grant_user_date",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SharingGrant(Base):
    __tablename__ = "sharing_grants"
    __table_args__ = (
        # App-level check enforces only one active grant per (granting, granted, team).
        # For PostgreSQL, a partial unique index (WHERE revoked_at IS NULL) should
        # be added via Alembic migration.
        UniqueConstraint(
            "granting_leader_id",
            "granted_to_leader_id",
            "team_id",
            name="uq_sharing_grant_leaders_team",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    granting_leader_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    granted_to_leader_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
