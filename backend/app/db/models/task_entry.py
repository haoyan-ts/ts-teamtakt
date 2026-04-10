import enum
import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class TaskStatus(enum.StrEnum):
    todo = "todo"
    running = "running"
    done = "done"
    blocked = "blocked"


class TaskEntry(Base):
    __tablename__ = "task_entries"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    daily_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("daily_records.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    sub_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("category_sub_types.id"), nullable=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    effort: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status", native_enum=False), nullable=False
    )
    blocker_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("blocker_types.id"), nullable=True
    )
    blocker_text: Mapped[str] = mapped_column(Text, nullable=True)
    carried_from_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_entries.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class TaskEntrySelfAssessmentTag(Base):
    __tablename__ = "task_entry_self_assessment_tags"
    __table_args__ = (
        UniqueConstraint(
            "task_entry_id", "self_assessment_tag_id", name="uq_task_entry_tag"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_entries.id"), nullable=False
    )
    self_assessment_tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("self_assessment_tags.id"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)
