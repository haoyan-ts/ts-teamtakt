from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


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


class UserUpdate(BaseModel):
    display_name: str | None = None
    preferred_locale: Literal["en", "ja", "zh", "ko"] | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_not_empty(cls, v: str | None) -> str | None:
        if v is not None and (not v.strip() or len(v) > 100):
            raise ValueError("display_name must be 1–100 non-whitespace characters")
        return v
