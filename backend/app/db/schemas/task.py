from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.db.models.task import EnergyType, TaskPriority, TaskStatus

_FIBONACCI = frozenset({1, 2, 3, 5, 8})


def _validate_fibonacci(v: int) -> int:
    if v not in _FIBONACCI:
        raise ValueError(f"effort must be one of {sorted(_FIBONACCI)}, got {v}")
    return v


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
    effort: int
    energy_type: EnergyType | None = None
    insight: str | None = None
    blocker_text: str | None = None
    sort_order: int = 0
    self_assessment_tags: list[SelfAssessmentTagRef] = []

    @field_validator("effort")
    @classmethod
    def effort_must_be_fibonacci(cls, v: int) -> int:
        return _validate_fibonacci(v)

    @field_validator("insight")
    @classmethod
    def insight_max_500(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise ValueError("insight must be 500 characters or fewer")
        return v


class DailyWorkLogResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    daily_record_id: uuid.UUID
    effort: int
    energy_type: EnergyType | None
    insight: str | None
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
    project_id: uuid.UUID | None = None
    category_id: uuid.UUID
    work_type_id: uuid.UUID | None = None
    status: Literal["todo", "running", "done", "blocked"] = "todo"
    priority: TaskPriority | None = None
    estimated_effort: int | None = None
    due_date: date | None = None
    blocker_type_id: uuid.UUID | None = None
    github_issue_url: str | None = None
    github_status: str | None = None
    insight: str | None = None

    @field_validator("estimated_effort")
    @classmethod
    def estimated_effort_must_be_fibonacci(cls, v: int | None) -> int | None:
        if v is not None:
            return _validate_fibonacci(v)
        return v

    @field_validator("insight")
    @classmethod
    def insight_max_500(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise ValueError("insight must be 500 characters or fewer")
        return v


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    work_type_id: uuid.UUID | None = None
    status: Literal["todo", "running", "done", "blocked"] | None = None
    priority: TaskPriority | None = None
    estimated_effort: int | None = None
    due_date: date | None = None
    blocker_type_id: uuid.UUID | None = None
    github_issue_url: str | None = None
    github_status: str | None = None
    is_active: bool | None = None
    insight: str | None = None

    @field_validator("estimated_effort")
    @classmethod
    def estimated_effort_must_be_fibonacci(cls, v: int | None) -> int | None:
        if v is not None:
            return _validate_fibonacci(v)
        return v

    @field_validator("insight")
    @classmethod
    def insight_max_500(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise ValueError("insight must be 500 characters or fewer")
        return v


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    assignee_id: uuid.UUID
    project_id: uuid.UUID | None
    category_id: uuid.UUID
    work_type_id: uuid.UUID | None
    status: str
    priority: TaskPriority | None
    estimated_effort: int | None
    due_date: date | None
    blocker_type_id: uuid.UUID | None
    github_issue_url: str | None
    github_status: str | None
    insight: str | None
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
    work_type_id: uuid.UUID | None = None
    estimated_effort: int | None = None
    insight: str | None = None
    # github_status is the raw GitHub Project board column (e.g. "In Progress").
    # status is the derived teamtakt internal value mapped from github_status.
    github_status: str | None = None
    status: TaskStatus = TaskStatus.todo
