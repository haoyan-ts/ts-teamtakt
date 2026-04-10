import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    VARCHAR,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from . import Base


class QuarterlyReportStatus(enum.StrEnum):
    generating = "generating"
    draft = "draft"
    finalized = "finalized"


class QuarterlyReport(Base):
    __tablename__ = "quarterly_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "quarter", name="uq_quarterly_report_user_quarter"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    quarter: Mapped[str] = mapped_column(VARCHAR(6), nullable=False)  # e.g. "2026Q1"
    status: Mapped[QuarterlyReportStatus] = mapped_column(
        SAEnum(
            QuarterlyReportStatus,
            name="quarterly_report_status",
            native_enum=False,
        ),
        nullable=False,
        default=QuarterlyReportStatus.generating,
    )
    # Pre-aggregated stats (system-generated, not user content)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # LLM-generated sections
    sections: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # User-provided guidance (untrusted, capped at 2000 chars)
    guidance_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(
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
