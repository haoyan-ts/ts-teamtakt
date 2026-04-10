from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    scope: Literal["personal", "team", "cross_team"]
    team_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    scope: str
    team_id: uuid.UUID | None
    created_by: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
