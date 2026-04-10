import uuid
from datetime import datetime

from pydantic import BaseModel


class SharingGrantCreate(BaseModel):
    granted_to_leader_id: uuid.UUID
    # team_id is inferred from the granting leader's current team


class SharingGrantResponse(BaseModel):
    id: uuid.UUID
    granting_leader_id: uuid.UUID
    granted_to_leader_id: uuid.UUID
    team_id: uuid.UUID
    granted_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}
