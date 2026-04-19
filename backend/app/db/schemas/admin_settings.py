from __future__ import annotations

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
