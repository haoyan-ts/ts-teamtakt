from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Overload
# ---------------------------------------------------------------------------


class OverloadEntry(BaseModel):
    user_id: uuid.UUID
    display_name: str
    streak_start: date
    streak_end: date
    max_load: int


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------


class BlockerByType(BaseModel):
    type: str
    count: int


class RecurringBlocker(BaseModel):
    task_desc: str
    project: str
    days_blocked: int


class BlockerSummary(BaseModel):
    by_type: list[BlockerByType]
    recurring: list[RecurringBlocker]


# ---------------------------------------------------------------------------
# Fragmentation
# ---------------------------------------------------------------------------


class FragmentationEntry(BaseModel):
    user_id: uuid.UUID
    display_name: str
    date: date
    task_count: int


# ---------------------------------------------------------------------------
# Carry-over aging
# ---------------------------------------------------------------------------


class CarryoverAgingEntry(BaseModel):
    user_id: uuid.UUID
    display_name: str
    task_desc: str
    project: str
    root_date: date
    working_days_aged: int


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------


class MemberBalance(BaseModel):
    user_id: uuid.UUID
    display_name: str
    categories: dict[str, float]


class TeamBalance(BaseModel):
    members: list[MemberBalance]
    team_aggregate: dict[str, float]
    targets: dict[str, int]


# ---------------------------------------------------------------------------
# Project effort
# ---------------------------------------------------------------------------


class MemberEffort(BaseModel):
    user_id: uuid.UUID
    display_name: str
    effort: int


class ProjectEffortEntry(BaseModel):
    project_id: uuid.UUID
    name: str
    scope: str
    total_effort: int
    member_effort: list[MemberEffort]


# ---------------------------------------------------------------------------
# Growth (personal)
# ---------------------------------------------------------------------------


class MonthlyBalance(BaseModel):
    month: str  # "YYYY-MM"
    categories: dict[str, float]


class WeeklyLoad(BaseModel):
    week_start: date
    avg_load: float


class MonthlyBlockerCount(BaseModel):
    month: str
    count: int


class GrowthResponse(BaseModel):
    balance_trend: list[MonthlyBalance]
    load_trend: list[WeeklyLoad]
    blocker_trend: list[MonthlyBlockerCount]
