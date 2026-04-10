from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Comment schemas
# ---------------------------------------------------------------------------


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    parent_comment_id: uuid.UUID | None = None


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CommentRead(BaseModel):
    id: uuid.UUID
    daily_record_id: uuid.UUID
    parent_comment_id: uuid.UUID | None
    author_id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime
    updated_at: datetime
    replies: list[CommentRead] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Reaction schemas
# ---------------------------------------------------------------------------


class ReactionCreate(BaseModel):
    emoji: str = Field(min_length=1, max_length=32)


class ReactionGroupRead(BaseModel):
    emoji: str
    count: int
    reacted_by_me: bool
    user_ids: list[uuid.UUID]


# ---------------------------------------------------------------------------
# Feed schemas
# ---------------------------------------------------------------------------


class FeedTaskEntry(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    project_id: uuid.UUID
    task_description: str
    effort: int
    status: str
    blocker_type_id: uuid.UUID | None
    # blocker_text intentionally omitted (private field)
    carried_from_id: uuid.UUID | None
    sort_order: int
    self_assessment_tags: list[dict] = []


class FeedItemRead(BaseModel):
    """Public view of a DailyRecord — private fields (day_load, blocker_text) omitted."""

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    record_date: str  # ISO date string
    day_note: str | None
    task_entries: list[FeedTaskEntry]
    comment_count: int
    reactions: list[ReactionGroupRead]
    created_at: datetime
    updated_at: datetime
