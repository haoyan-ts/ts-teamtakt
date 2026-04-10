"""GET /teams/{id}/settings  and  PATCH /teams/{id}/settings"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.engine import get_db
from app.db.models.team import TeamMembership, TeamSettings
from app.db.models.user import User
from app.db.schemas.team_settings import TeamSettingsResponse, TeamSettingsUpdate

router = APIRouter(prefix="/teams", tags=["team-settings"])


async def _require_leader_or_admin(
    team_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    if user.is_admin:
        return
    if not user.is_leader:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    r = await db.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == user.id,
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    if r.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a leader of this team"
        )


@router.get("/{team_id}/settings", response_model=TeamSettingsResponse)
async def get_team_settings(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    r = await db.execute(select(TeamSettings).where(TeamSettings.team_id == team_id))
    settings = r.scalar_one_or_none()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found"
        )
    return TeamSettingsResponse.model_validate(settings)


@router.patch("/{team_id}/settings", response_model=TeamSettingsResponse)
async def update_team_settings(
    team_id: uuid.UUID,
    body: TeamSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    r = await db.execute(select(TeamSettings).where(TeamSettings.team_id == team_id))
    settings = r.scalar_one_or_none()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found"
        )

    if body.overload_load_threshold is not None:
        settings.overload_load_threshold = body.overload_load_threshold
    if body.overload_streak_days is not None:
        settings.overload_streak_days = body.overload_streak_days
    if body.fragmentation_task_threshold is not None:
        settings.fragmentation_task_threshold = body.fragmentation_task_threshold
    if body.carryover_aging_days is not None:
        settings.carryover_aging_days = body.carryover_aging_days
    if body.balance_targets is not None:
        settings.balance_targets = body.balance_targets

    await db.commit()
    await db.refresh(settings)
    return TeamSettingsResponse.model_validate(settings)
