from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.db.schemas.task import DailyWorkLogCreate, DailyWorkLogResponse


class EnergyTypeEffort(BaseModel):
    energy_type: str | None  # None for work logs without energy_type set
    effort: int


class DailyEffortBreakdownResponse(BaseModel):
    user_id: uuid.UUID
    record_date: date
    total_effort: int
    by_energy_type: list[EnergyTypeEffort]
    battery_pct: int | None  # None when visibility rules disallow it


class DailyRecordCreate(BaseModel):
    record_date: date
    day_load: int = Field(ge=0, le=100)  # battery %, 0–100
    day_insight: str | None = None
    form_opened_at: datetime
    daily_work_logs: list[DailyWorkLogCreate] = []


class DailyRecordUpdate(BaseModel):
    day_load: int | None = Field(default=None, ge=0, le=100)  # battery %, 0–100
    day_insight: str | None = None
    form_opened_at: datetime  # required on update too (for edit window check)
    daily_work_logs: list[DailyWorkLogCreate] | None = None  # full replacement


class DailyRecordResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    record_date: date
    day_load: int | None  # None when requester lacks visibility
    day_insight: str | None
    form_opened_at: datetime
    is_checked: bool
    teams_message_sent_at: datetime | None
    email_sent_at: datetime | None
    is_locked: bool  # computed: is_checked OR now >= edit_deadline; never stored
    created_at: datetime
    updated_at: datetime
    daily_work_logs: list[DailyWorkLogResponse] = []

    model_config = {"from_attributes": False}


class DailyRecordCheckRequest(BaseModel):
    form_opened_at: datetime  # required; edit-window check happens at submit time


class DailyStatusDraftResponse(BaseModel):
    subject: str
    body: str


class DailyStatusSendRequest(BaseModel):
    subject: str
    body: str  # user-edited content; HTML-escaped at send time


class DailyTeamsMessageSentResponse(BaseModel):
    sent_at: datetime
    message_id: str | None


class DailyEmailSentResponse(BaseModel):
    sent_at: datetime


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
