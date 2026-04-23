from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    github_project_node_id: str
    github_project_number: int | None = None
    github_project_owner: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    github_project_number: int | None = None
    github_project_owner: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    github_project_node_id: str
    github_project_number: int | None
    github_project_owner: str | None
    created_by: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GitHubAvailableProjectItem(BaseModel):
    node_id: str
    number: int
    title: str
    owner_login: str
    url: str
