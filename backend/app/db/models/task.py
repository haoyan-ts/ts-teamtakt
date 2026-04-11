import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class TaskStatus(enum.StrEnum):
    todo = "todo"
    running = "running"
    done = "done"
    blocked = "blocked"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index(
            "uq_task_github_issue_url",
            "assignee_id",
            "github_issue_url",
            unique=True,
            postgresql_where=text("github_issue_url IS NOT NULL"),
            sqlite_where=text("github_issue_url IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    sub_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("category_sub_types.id"), nullable=True
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status", native_enum=False), nullable=False
    )
    estimated_effort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blocker_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("blocker_types.id"), nullable=True
    )
    github_issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DailyWorkLog(Base):
    __tablename__ = "daily_work_logs"
    __table_args__ = (
        UniqueConstraint("task_id", "daily_record_id", name="uq_dwl_task_record"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.id"), nullable=False
    )
    daily_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("daily_records.id"), nullable=False
    )
    effort: Mapped[int] = mapped_column(Integer, nullable=False)
    work_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocker_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("blocker_types.id"), nullable=True
    )
    blocker_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyWorkLogSelfAssessmentTag(Base):
    __tablename__ = "daily_work_log_self_assessment_tags"
    __table_args__ = (
        UniqueConstraint(
            "daily_work_log_id",
            "self_assessment_tag_id",
            name="uq_dwl_tag",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    daily_work_log_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("daily_work_logs.id"), nullable=False
    )
    self_assessment_tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("self_assessment_tags.id"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)
