import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user
from app.db.engine import get_db
from app.db.models.notification import Notification
from app.db.models.project import Project, ProjectScope
from app.db.models.team import TeamMembership
from app.db.models.user import User
from app.db.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter()


async def _get_user_team(user: User, db: AsyncSession) -> uuid.UUID | None:
    result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == user.id,
            TeamMembership.left_at.is_(None),
        )
    )
    m = result.scalar_one_or_none()
    return m.team_id if m else None


@router.post(
    "/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED
)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if body.scope == "cross_team":
        if not (current_user.is_leader or current_user.is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Leader or admin required for cross-team projects",
            )
        team_id = None
    else:
        team_id = await _get_user_team(current_user, db)

    project = Project(
        id=uuid.uuid4(),
        name=body.name,
        scope=ProjectScope(body.scope),
        team_id=team_id,
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

    user_team_id = await _get_user_team(current_user, db)

    from sqlalchemy import or_

    conditions = or_(
        # Own personal projects
        (Project.scope == ProjectScope.personal)
        & (Project.created_by == current_user.id),
        # Own team projects
        (Project.scope == ProjectScope.team) & (Project.team_id == user_team_id),
        # All cross-team projects
        Project.scope == ProjectScope.cross_team,
    )

    q = select(Project).where(conditions)
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

    user_team_id = await _get_user_team(current_user, db)

    if project.scope == ProjectScope.personal:
        if project.created_by != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
    elif project.scope == ProjectScope.team:
        if not current_user.is_admin and project.team_id != user_team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
    # cross_team: any authenticated user may read

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

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/promote", response_model=ProjectResponse)
async def promote_project(
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

    if project.scope != ProjectScope.team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only team-scoped projects can be promoted",
        )

    # Must be admin OR (leader AND member of the project's team)
    is_authorized = current_user.is_admin
    if not is_authorized and current_user.is_leader:
        membership_result = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.team_id == project.team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        if membership_result.scalar_one_or_none() is not None:
            is_authorized = True

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project's team leader or admin can promote",
        )

    project.scope = ProjectScope.cross_team
    project.team_id = None

    notification = Notification(
        id=uuid.uuid4(),
        user_id=project.created_by,
        trigger_type="project_promoted",
        title="Your project was promoted to cross-team",
        data={"project_id": str(project_id)},
    )
    db.add(notification)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)
