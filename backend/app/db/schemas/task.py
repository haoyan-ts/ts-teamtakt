from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Self-assessment tag refs (shared between request and response)
# ---------------------------------------------------------------------------


class SelfAssessmentTagRef(BaseModel):
    self_assessment_tag_id: uuid.UUID
    is_primary: bool


class SelfAssessmentTagRefResponse(BaseModel):
    self_assessment_tag_id: uuid.UUID
    is_primary: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# DailyWorkLog schemas
# ---------------------------------------------------------------------------


class DailyWorkLogCreate(BaseModel):
    task_id: uuid.UUID
    effort: int = Field(ge=1, le=5)
    work_note: str | None = None
    blocker_type_id: uuid.UUID | None = None
    blocker_text: str | None = None
    sort_order: int = 0
    self_assessment_tags: list[SelfAssessmentTagRef] = []


class DailyWorkLogResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    daily_record_id: uuid.UUID
    effort: int
    work_note: str | None
    blocker_type_id: uuid.UUID | None
    blocker_text: str | None
    sort_order: int
    self_assessment_tags: list[SelfAssessmentTagRefResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: uuid.UUID
    category_id: uuid.UUID
    sub_type_id: uuid.UUID | None = None
    status: Literal["todo", "running", "done", "blocked"] = "todo"
    estimated_effort: int | None = Field(default=None, ge=1, le=5)
    blocker_type_id: uuid.UUID | None = None
    github_issue_url: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    sub_type_id: uuid.UUID | None = None
    status: Literal["todo", "running", "done", "blocked"] | None = None
    estimated_effort: int | None = Field(default=None, ge=1, le=5)
    blocker_type_id: uuid.UUID | None = None
    github_issue_url: str | None = None
    is_active: bool | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    assignee_id: uuid.UUID
    project_id: uuid.UUID
    category_id: uuid.UUID
    sub_type_id: uuid.UUID | None
    status: str
    estimated_effort: int | None
    blocker_type_id: uuid.UUID | None
    github_issue_url: str | None
    created_by: uuid.UUID
    created_at: datetime
    closed_at: date | None
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# GitHub auto-fill response (placeholder — implementation deferred)
# ---------------------------------------------------------------------------


class TaskAutoFillResponse(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    sub_type_id: uuid.UUID | None = None
    estimated_effort: int | None = None
