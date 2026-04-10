from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel


class WeeklyReportData(BaseModel):
    days_reported: int
    total_tasks: int
    avg_day_load: float
    category_breakdown: dict[str, int]
    sub_type_breakdown: dict[str, int]
    top_projects: list[dict[str, Any]]
    carry_overs: list[dict[str, Any]]
    blockers: list[dict[str, Any]]
    tag_distribution: dict[str, int]


class WeeklyReportResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    data: WeeklyReportData
    created_at: str

    model_config = {"from_attributes": True}


class WeeklyReportSummaryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    data: dict[str, Any]
    created_at: str

    model_config = {"from_attributes": True}


class EmailDraftBodySections(BaseModel):
    tasks: str = ""
    successes: str = ""
    next_week: str = ""


class WeeklyEmailDraftResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    subject: str
    body_sections: EmailDraftBodySections
    status: str
    idempotency_key: str
    sent_at: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class WeeklyEmailDraftUpdate(BaseModel):
    subject: str | None = None
    body_sections: EmailDraftBodySections | None = None
