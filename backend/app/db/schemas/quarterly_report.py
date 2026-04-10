from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QuarterlyReportGenerate(BaseModel):
    quarter: str = Field(pattern=r"^\d{4}Q[1-4]$", description="e.g. '2026Q1'")
    guidance_text: str | None = Field(default=None, max_length=2000)


class QuarterlyReportUpdate(BaseModel):
    sections: dict | None = None
    guidance_text: str | None = Field(default=None, max_length=2000)


class QuarterlyReportRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    quarter: str
    status: str
    data: dict | None
    sections: dict | None
    guidance_text: str | None
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
