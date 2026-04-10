from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class TeamSettingsResponse(BaseModel):
    team_id: uuid.UUID
    overload_load_threshold: int
    overload_streak_days: int
    fragmentation_task_threshold: int
    carryover_aging_days: int
    balance_targets: dict[str, int]

    model_config = {"from_attributes": True}


class TeamSettingsUpdate(BaseModel):
    overload_load_threshold: int | None = Field(None, ge=1, le=5)
    overload_streak_days: int | None = Field(None, ge=1)
    fragmentation_task_threshold: int | None = Field(None, ge=1)
    carryover_aging_days: int | None = Field(None, ge=1)
    balance_targets: dict[str, int] | None = None
