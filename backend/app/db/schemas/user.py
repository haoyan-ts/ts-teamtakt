from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_leader: bool
    is_admin: bool
    preferred_locale: str
    created_at: datetime | None = None
    team: dict | None = None

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    is_leader: bool | None = None
    is_admin: bool | None = None
