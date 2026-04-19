import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

# Fixed UUIDs for the 4 default absence types — shared by migration and seed.
ABSENCE_TYPE_UUIDS: dict[str, uuid.UUID] = {
    "holiday": uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
    "exchanged_holiday": uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901"),
    "illness": uuid.UUID("c3d4e5f6-a7b8-9012-cdef-123456789012"),
    "other": uuid.UUID("d4e5f6a7-b8c9-0123-defa-234567890123"),
}


class AbsenceType(Base):
    __tablename__ = "absence_types"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


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
    absence_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("absence_types.id"), nullable=False
    )
    absence_type: Mapped["AbsenceType"] = relationship("AbsenceType", lazy="joined")
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
