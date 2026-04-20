from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user, require_active_user
from app.db.engine import get_db
from app.db.models.task import Task, TaskStatus
from app.db.models.user import User
from app.db.schemas.task import (
    TaskAutoFillResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.github_autofill import fetch_github_issue, map_to_task_fields

router = APIRouter(tags=["tasks"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_task_or_404(task_id: uuid.UUID, db: AsyncSession) -> Task:
    r = await db.execute(select(Task).where(Task.id == task_id))
    task = r.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return task


async def _require_task_owner_or_admin(task: Task, user: User) -> None:
    if task.assignee_id != user.id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Enforce UNIQUE(assignee_id, github_issue_url) at app level
    if body.github_issue_url is not None:
        dup = await db.scalar(
            select(Task).where(
                Task.assignee_id == current_user.id,
                Task.github_issue_url == body.github_issue_url,
                Task.is_active.is_(True),
            )
        )
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A task linked to this GitHub issue URL already exists for this user.",
            )

    task_status = TaskStatus(body.status)
    closed_at: date | None = date.today() if task_status == TaskStatus.done else None

    task = Task(
        id=__import__("uuid").uuid4(),
        title=body.title,
        description=body.description,
        assignee_id=current_user.id,
        created_by=current_user.id,
        project_id=body.project_id,
        category_id=body.category_id,
        sub_type_id=body.sub_type_id,
        status=task_status,
        estimated_effort=body.estimated_effort,
        blocker_type_id=body.blocker_type_id,
        github_issue_url=body.github_issue_url,
        closed_at=closed_at,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    assignee_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    project_id: uuid.UUID | None = Query(default=None),
    is_active: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Determine whose tasks to return
    target_id = assignee_id if assignee_id is not None else current_user.id

    # Non-admin non-leaders can only see their own tasks
    if (
        target_id != current_user.id
        and not current_user.is_admin
        and not current_user.is_leader
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    stmt = select(Task).where(
        Task.assignee_id == target_id, Task.is_active == is_active
    )
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    stmt = stmt.order_by(Task.created_at.desc())

    r = await db.execute(stmt)
    return r.scalars().all()


@router.get("/tasks/autofill", response_model=TaskAutoFillResponse)
async def task_autofill(
    url: str = Query(..., description="GitHub issue URL"),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a GitHub issue and return prefill data for task creation."""
    try:
        issue = await fetch_github_issue(url, github_token=settings.GITHUB_TOKEN)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return await map_to_task_fields(issue, db)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_task_or_404(task_id, db)
    await _require_task_owner_or_admin(task, current_user)
    return task


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_task_or_404(task_id, db)
    await _require_task_owner_or_admin(task, current_user)

    # Enforce github_issue_url immutability after first set
    if body.github_issue_url is not None and task.github_issue_url is not None:
        if body.github_issue_url != task.github_issue_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="github_issue_url is immutable after it has been set.",
            )

    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.project_id is not None:
        task.project_id = body.project_id
    if body.category_id is not None:
        task.category_id = body.category_id
    if body.sub_type_id is not None:
        task.sub_type_id = body.sub_type_id
    if body.estimated_effort is not None:
        task.estimated_effort = body.estimated_effort
    if body.blocker_type_id is not None:
        task.blocker_type_id = body.blocker_type_id
    if body.is_active is not None:
        task.is_active = body.is_active
    if body.insight is not None:
        task.insight = body.insight

    if body.status is not None:
        new_status = TaskStatus(body.status)
        task.status = new_status
        if new_status == TaskStatus.done and task.closed_at is None:
            task.closed_at = date.today()
        elif new_status != TaskStatus.done:
            task.closed_at = None

    if body.github_issue_url is not None and task.github_issue_url is None:
        # Validate uniqueness before setting for the first time
        dup = await db.scalar(
            select(Task).where(
                Task.assignee_id == task.assignee_id,
                Task.github_issue_url == body.github_issue_url,
                Task.is_active.is_(True),
                Task.id != task.id,
            )
        )
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A task linked to this GitHub issue URL already exists for this user.",
            )
        task.github_issue_url = body.github_issue_url

    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_task_or_404(task_id, db)
    await _require_task_owner_or_admin(task, current_user)
    task.is_active = False
    await db.commit()
