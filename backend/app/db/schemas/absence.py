from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AbsenceTypeCreate(BaseModel):
    name: str


class AbsenceTypeUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class AbsenceTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class AbsenceCreate(BaseModel):
    record_date: date
    absence_type_id: uuid.UUID
    note: str | None = None
    form_opened_at: datetime  # required for edit window check


class AbsenceUpdate(BaseModel):
    absence_type_id: uuid.UUID | None = None
    note: str | None = None
    form_opened_at: datetime  # required for edit window check


class AbsenceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    record_date: date
    absence_type: AbsenceTypeResponse
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
