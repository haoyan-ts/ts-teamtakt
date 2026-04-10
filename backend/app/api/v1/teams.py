import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.db.engine import get_db
from app.db.models.team import (
    JoinRequestStatus,
    Team,
    TeamJoinRequest,
    TeamMembership,
    TeamSettings,
)
from app.db.models.user import User
from app.db.schemas.join_request import JoinRequestAction, JoinRequestResponse
from app.db.schemas.team import (
    AssignMemberRequest,
    TeamCreate,
    TeamMemberResponse,
    TeamResponse,
)

router = APIRouter(prefix="/teams", tags=["teams"])


async def _require_team_leader_or_admin(
    team_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """Allow admins unconditionally; leaders must have an active membership in this team."""
    if user.is_admin:
        return
    if not user.is_leader:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leader or admin access required",
        )
    result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == user.id,
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a leader of this team",
        )


# ---------------------------------------------------------------------------
# Teams (admin only)
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TeamResponse)
async def create_team(
    body: TeamCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    team = Team(name=body.name)
    db.add(team)
    await db.flush()
    db.add(TeamSettings(team_id=team.id))
    await db.commit()
    await db.refresh(team)
    return TeamResponse(id=team.id, name=team.name, created_at=team.created_at)


@router.get("", response_model=list[TeamResponse])
async def list_teams(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Team))
    teams = result.scalars().all()

    responses: list[TeamResponse] = []
    for team in teams:
        count_result = await db.execute(
            select(func.count())
            .select_from(TeamMembership)
            .where(
                TeamMembership.team_id == team.id,
                TeamMembership.left_at.is_(None),
            )
        )
        member_count = count_result.scalar() or 0

        leaders_result = await db.execute(
            select(User)
            .join(TeamMembership, User.id == TeamMembership.user_id)
            .where(
                TeamMembership.team_id == team.id,
                TeamMembership.left_at.is_(None),
                User.is_leader,
            )
        )
        leaders = [u.display_name for u in leaders_result.scalars().all()]

        responses.append(
            TeamResponse(
                id=team.id,
                name=team.name,
                created_at=team.created_at,
                member_count=member_count,
                leaders=leaders,
            )
        )
    return responses


@router.delete("/{team_id}", status_code=status.HTTP_200_OK)
async def delete_team(
    team_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    active = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    if active.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Remove or reassign all members and the leader before dissolving this team.",
        )

    await db.delete(team)
    await db.commit()
    return {"message": "Team deleted"}


# ---------------------------------------------------------------------------
# Join Requests
# ---------------------------------------------------------------------------


@router.post("/{team_id}/join-requests", status_code=status.HTTP_201_CREATED)
async def create_join_request(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Team).where(Team.id == team_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    existing = await db.execute(
        select(TeamJoinRequest).where(
            TeamJoinRequest.user_id == current_user.id,
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == JoinRequestStatus.pending,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pending join request already exists",
        )

    req = TeamJoinRequest(
        user_id=current_user.id,
        team_id=team_id,
        status=JoinRequestStatus.pending,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return JoinRequestResponse.model_validate(req)


@router.get("/{team_id}/join-requests", response_model=list[JoinRequestResponse])
async def list_join_requests(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_team_leader_or_admin(team_id, current_user, db)

    result = await db.execute(
        select(TeamJoinRequest).where(
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == JoinRequestStatus.pending,
        )
    )
    return [JoinRequestResponse.model_validate(r) for r in result.scalars().all()]


@router.patch("/{team_id}/join-requests/{req_id}")
async def resolve_join_request(
    team_id: uuid.UUID,
    req_id: uuid.UUID,
    body: JoinRequestAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_team_leader_or_admin(team_id, current_user, db)

    result = await db.execute(
        select(TeamJoinRequest).where(
            TeamJoinRequest.id == req_id,
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == JoinRequestStatus.pending,
        )
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found"
        )

    now = datetime.now(UTC)
    req.resolved_at = now
    req.resolved_by = current_user.id

    if body.action == "approve":
        req.status = JoinRequestStatus.approved

        # Close any existing active membership (team transfer)
        old = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == req.user_id,
                TeamMembership.left_at.is_(None),
            )
        )
        old_membership = old.scalar_one_or_none()
        if old_membership is not None:
            old_membership.left_at = now

        db.add(TeamMembership(user_id=req.user_id, team_id=team_id, joined_at=now))
    else:
        req.status = JoinRequestStatus.rejected

    await db.commit()
    await db.refresh(req)
    return JoinRequestResponse.model_validate(req)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{team_id}/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_team_leader_or_admin(team_id, current_user, db)

    result = await db.execute(
        select(User, TeamMembership)
        .join(TeamMembership, User.id == TeamMembership.user_id)
        .where(
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    return [
        TeamMemberResponse(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            is_leader=user.is_leader,
            joined_at=membership.joined_at,
        )
        for user, membership in result.all()
    ]


@router.post("/{team_id}/members", status_code=status.HTTP_201_CREATED)
async def admin_assign_member(
    team_id: uuid.UUID,
    body: AssignMemberRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    if team_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    user_result = await db.execute(select(User).where(User.id == body.user_id))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    now = datetime.now(UTC)

    old = await db.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == body.user_id,
            TeamMembership.left_at.is_(None),
        )
    )
    old_membership = old.scalar_one_or_none()
    if old_membership is not None:
        old_membership.left_at = now

    new_membership = TeamMembership(
        user_id=body.user_id, team_id=team_id, joined_at=now
    )
    db.add(new_membership)
    await db.commit()
    await db.refresh(new_membership)
    return {"message": "Member assigned", "membership_id": str(new_membership.id)}
