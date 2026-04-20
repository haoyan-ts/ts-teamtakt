from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.db.schemas.task import DailyWorkLogCreate, DailyWorkLogResponse


class DailyRecordCreate(BaseModel):
    record_date: date
    day_load: int = Field(ge=0, le=100)  # battery %, 0–100
    day_note: str | None = None
    form_opened_at: datetime
    daily_work_logs: list[DailyWorkLogCreate] = []


class DailyRecordUpdate(BaseModel):
    day_load: int | None = Field(default=None, ge=0, le=100)  # battery %, 0–100
    day_note: str | None = None
    form_opened_at: datetime  # required on update too (for edit window check)
    daily_work_logs: list[DailyWorkLogCreate] | None = None  # full replacement


class DailyRecordResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    record_date: date
    day_load: int | None  # None when requester lacks visibility
    day_note: str | None
    form_opened_at: datetime
    created_at: datetime
    updated_at: datetime
    daily_work_logs: list[DailyWorkLogResponse] = []

    model_config = {"from_attributes": True}


class UnlockGrantCreate(BaseModel):
    user_id: uuid.UUID
    record_date: date


class UnlockGrantResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    record_date: date
    granted_by: uuid.UUID
    granted_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}
