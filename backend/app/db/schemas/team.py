from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime | None = None
    member_count: int = 0
    leaders: list[str] = []

    model_config = {"from_attributes": True}


class TeamMemberResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    is_leader: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


class AssignMemberRequest(BaseModel):
    user_id: uuid.UUID
