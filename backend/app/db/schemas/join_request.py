from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.db.models.team import JoinRequestStatus


class JoinRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    team_id: uuid.UUID
    status: JoinRequestStatus
    requested_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class JoinRequestAction(BaseModel):
    action: Literal["approve", "reject"]
