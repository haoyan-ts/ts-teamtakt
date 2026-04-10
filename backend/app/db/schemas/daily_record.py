from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SelfAssessmentTagRef(BaseModel):
    self_assessment_tag_id: uuid.UUID
    is_primary: bool


class TaskEntryCreate(BaseModel):
    category_id: uuid.UUID
    sub_type_id: uuid.UUID | None = None
    project_id: uuid.UUID
    task_description: str
    effort: int = Field(ge=1, le=5)
    status: Literal["todo", "running", "done", "blocked"]
    blocker_type_id: uuid.UUID | None = None
    blocker_text: str | None = None
    carried_from_id: uuid.UUID | None = None
    sort_order: int = 0
    self_assessment_tags: list[SelfAssessmentTagRef] = []


class TaskEntryUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    sub_type_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    task_description: str | None = None
    effort: int | None = Field(default=None, ge=1, le=5)
    status: Literal["todo", "running", "done", "blocked"] | None = None
    blocker_type_id: uuid.UUID | None = None
    blocker_text: str | None = None
    # carried_from_id OMITTED — immutable after creation
    sort_order: int | None = None
    self_assessment_tags: list[SelfAssessmentTagRef] | None = None


class DailyRecordCreate(BaseModel):
    record_date: date
    day_load: int = Field(ge=1, le=5)
    day_note: str | None = None
    form_opened_at: datetime
    task_entries: list[TaskEntryCreate] = []


class DailyRecordUpdate(BaseModel):
    day_load: int | None = Field(default=None, ge=1, le=5)
    day_note: str | None = None
    form_opened_at: datetime  # required on update too (for edit window check)
    task_entries: list[TaskEntryCreate] | None = None  # full replacement of task list


# ---- Response schemas ----


class SelfAssessmentTagRefResponse(BaseModel):
    self_assessment_tag_id: uuid.UUID
    is_primary: bool

    model_config = {"from_attributes": True}


class TaskEntryResponse(BaseModel):
    id: uuid.UUID
    daily_record_id: uuid.UUID
    category_id: uuid.UUID
    sub_type_id: uuid.UUID | None
    project_id: uuid.UUID
    task_description: str
    effort: int
    status: str
    blocker_type_id: uuid.UUID | None
    blocker_text: str | None
    carried_from_id: uuid.UUID | None
    sort_order: int
    self_assessment_tags: list[SelfAssessmentTagRefResponse] = []

    model_config = {"from_attributes": True}


class DailyRecordResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    record_date: date
    day_load: int | None  # None when requester lacks visibility
    day_note: str | None
    form_opened_at: datetime
    created_at: datetime
    updated_at: datetime
    task_entries: list[TaskEntryResponse] = []

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
