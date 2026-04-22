from __future__ import annotations

import uuid

from pydantic import BaseModel, field_validator

_ALLOWED_LANGUAGES = {"en", "ja", "ko", "zh"}


class AdminSettingsResponse(BaseModel):
    output_language: str


class AdminSettingsUpdate(BaseModel):
    output_language: str | None = None

    @field_validator("output_language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_LANGUAGES:
            raise ValueError(
                f"output_language must be one of {sorted(_ALLOWED_LANGUAGES)}"
            )
        return v


class TeamsConfigResponse(BaseModel):
    team_id: uuid.UUID
    teams_channel_id: str | None
    teams_team_id: str | None


class TeamsConfigUpsert(BaseModel):
    teams_channel_id: str | None = None
    teams_team_id: str | None = None
