import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user
from app.db.engine import get_db
from app.db.models.project import Project
from app.db.models.user import User
from app.db.schemas.project import (
    GitHubAvailableProjectItem,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.github_autofill import resolve_github_token
from app.services.github_projects import fetch_available_github_projects

router = APIRouter()


@router.post(
    "/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED
)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    existing = await db.execute(
        select(Project).where(
            Project.github_project_node_id == body.github_project_node_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A project with this GitHub Project node ID already exists",
        )

    project = Project(
        id=uuid.uuid4(),
        name=body.name,
        github_project_node_id=body.github_project_node_id,
        github_project_number=body.github_project_number,
        github_project_owner=body.github_project_owner,
        created_by=current_user.id,
        is_active=True,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if include_inactive and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    q = select(Project)
    if not current_user.is_admin:
        q = q.where(Project.created_by == current_user.id)
    if not include_inactive:
        q = q.where(Project.is_active.is_(True))

    result = await db.execute(q)
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    if project.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    return ProjectResponse.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    if project.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this project",
        )

    if body.name is not None:
        project.name = body.name
    if body.is_active is not None:
        project.is_active = body.is_active
    if body.github_project_number is not None:
        project.github_project_number = body.github_project_number
    if body.github_project_owner is not None:
        project.github_project_owner = body.github_project_owner

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get(
    "/projects/github/available", response_model=list[GitHubAvailableProjectItem]
)
async def list_available_github_projects(
    current_user: User = Depends(require_active_user),
) -> list[GitHubAvailableProjectItem]:
    """Return all GitHub Projects V2 accessible to the authenticated user.

    Requires the user to have a linked GitHub OAuth token.
    """
    if not current_user.github_access_token_enc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No GitHub account linked. Please connect your GitHub account first.",
        )

    github_token = await resolve_github_token(current_user)
    assert github_token is not None

    return await fetch_available_github_projects(github_token)
