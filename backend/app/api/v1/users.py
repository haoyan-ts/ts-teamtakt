import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.db.engine import get_db
from app.db.models.team import Team, TeamMembership
from app.db.models.user import User
from app.db.schemas.user import UserResponse, UserRoleUpdate, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TeamMembership, Team)
        .join(Team, TeamMembership.team_id == Team.id)
        .where(
            TeamMembership.user_id == current_user.id,
            TeamMembership.left_at.is_(None),
        )
    )
    row = result.first()
    team_data = None
    if row:
        _, team = row
        team_data = {"id": str(team.id), "name": team.name}

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "is_leader": current_user.is_leader,
        "is_admin": current_user.is_admin,
        "preferred_locale": current_user.preferred_locale,
        "team": team_data,
        "lobby": team_data is None,
    }


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.preferred_locale is not None:
        current_user.preferred_locale = body.preferred_locale

    await db.commit()
    await db.refresh(current_user)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        is_leader=current_user.is_leader,
        is_admin=current_user.is_admin,
        preferred_locale=current_user.preferred_locale,
        created_at=current_user.created_at,
    )


@router.get("", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User))
    users = result.scalars().all()

    responses: list[UserResponse] = []
    for user in users:
        team_result = await db.execute(
            select(Team)
            .join(TeamMembership, TeamMembership.team_id == Team.id)
            .where(
                TeamMembership.user_id == user.id,
                TeamMembership.left_at.is_(None),
            )
        )
        team = team_result.scalar_one_or_none()
        team_data = {"id": str(team.id), "name": team.name} if team else None

        responses.append(
            UserResponse(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                is_leader=user.is_leader,
                is_admin=user.is_admin,
                preferred_locale=user.preferred_locale,
                created_at=user.created_at,
                team=team_data,
            )
        )
    return responses


@router.patch("/{user_id}/roles")
async def update_roles(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if body.is_leader is not None:
        user.is_leader = body.is_leader
    if body.is_admin is not None:
        user.is_admin = body.is_admin

    await db.commit()
    await db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "is_leader": user.is_leader,
        "is_admin": user.is_admin,
    }
