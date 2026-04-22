from __future__ import annotations

import uuid

from pydantic import BaseModel


class SubTypeCreate(BaseModel):
    name: str
    sort_order: int = 0


class SubTypeUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class SubTypeResponse(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    sort_order: int
    sub_types: list[SubTypeResponse] = []

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    name: str


class TagUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class BlockerTypeCreate(BaseModel):
    name: str


class BlockerTypeUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class BlockerTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class WorkTypeCreate(BaseModel):
    name: str
    sort_order: int = 0


class WorkTypeUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class WorkTypeResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}
