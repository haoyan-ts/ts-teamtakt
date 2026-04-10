from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

AbsenceType = Literal["holiday", "exchanged_holiday", "illness", "other"]


class AbsenceCreate(BaseModel):
    record_date: date
    absence_type: AbsenceType
    note: str | None = None
    form_opened_at: datetime  # required for edit window check


class AbsenceUpdate(BaseModel):
    absence_type: AbsenceType | None = None
    note: str | None = None
    form_opened_at: datetime  # required for edit window check


class AbsenceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    record_date: date
    absence_type: str
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
