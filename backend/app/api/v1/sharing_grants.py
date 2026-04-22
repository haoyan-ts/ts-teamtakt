"""
Sharing grant endpoints — point-to-point, non-transitive leader-to-leader
read access for cross-team individual record data.

POST   /sharing-grants          — grant access (leader only, own team)
GET    /sharing-grants          — list active grants (granted by me + to me)
DELETE /sharing-grants/{id}     — revoke (granting leader or admin)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.engine import get_db
from app.db.models.grants import SharingGrant
from app.db.models.team import TeamMembership
from app.db.models.user import User
from app.db.schemas.sharing_grant import SharingGrantCreate, SharingGrantResponse

router = APIRouter(prefix="/sharing-grants", tags=["sharing-grants"])


async def _get_leader_team_id(user: User, db: AsyncSession) -> uuid.UUID:
    """Return the active team_id for a leader, or raise 403."""
    r = await db.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == user.id,
            TeamMembership.left_at.is_(None),
        )
    )
    mem = r.scalar_one_or_none()
    if mem is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of any team.",
        )
    return mem.team_id


@router.post("", response_model=SharingGrantResponse, status_code=201)
async def create_sharing_grant(
    body: SharingGrantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Grant another leader read access (including private fields) to your team.

    Constraints:
    - Only leaders may create grants, and only for their own team.
    - Non-transitivity: a leader cannot grant access to data they received via
      a sharing grant (they must be the direct team leader).
    - One active grant per (granter, grantee, team).
    """
    if not current_user.is_leader:
        raise HTTPException(status_code=403, detail="Leaders only.")

    team_id = await _get_leader_team_id(current_user, db)

    # Non-transitivity: ensure this leader is actually a *direct* leader of
    # the team — i.e., the team's data originates from their own team, not
    # from a sharing grant they received.  Since _get_leader_team_id confirms
    # active membership in this team, no further check is needed.

    # Ensure grantee is a leader
    r_grantee = await db.execute(
        select(User).where(User.id == body.granted_to_leader_id)
    )
    grantee = r_grantee.scalar_one_or_none()
    if grantee is None or not grantee.is_leader:
        raise HTTPException(
            status_code=400,
            detail="The grantee must be an existing leader.",
        )

    if body.granted_to_leader_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot grant access to yourself.")

    # Enforce one active grant per (granter, grantee, team)
    r_existing = await db.execute(
        select(SharingGrant).where(
            SharingGrant.granting_leader_id == current_user.id,
            SharingGrant.granted_to_leader_id == body.granted_to_leader_id,
            SharingGrant.team_id == team_id,
            SharingGrant.revoked_at.is_(None),
        )
    )
    if r_existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="An active sharing grant already exists for this combination.",
        )

    grant = SharingGrant(
        granting_leader_id=current_user.id,
        granted_to_leader_id=body.granted_to_leader_id,
        team_id=team_id,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


@router.get("", response_model=list[SharingGrantResponse])
async def list_sharing_grants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active grants where the current user is granter OR grantee."""
    if not (current_user.is_leader or current_user.is_admin):
        raise HTTPException(status_code=403, detail="Leaders and admins only.")

    r = await db.execute(
        select(SharingGrant).where(
            SharingGrant.revoked_at.is_(None),
            (
                (
                    (SharingGrant.granting_leader_id == current_user.id)
                    | (SharingGrant.granted_to_leader_id == current_user.id)
                )
                if not current_user.is_admin
                else true()
            ),
        )
    )
    return r.scalars().all()


@router.delete("/{grant_id}", status_code=204)
async def revoke_sharing_grant(
    grant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a sharing grant (granting leader or admin only)."""
    r = await db.execute(select(SharingGrant).where(SharingGrant.id == grant_id))
    grant = r.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail="Grant not found.")

    if not current_user.is_admin and grant.granting_leader_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Only the granting leader or admin may revoke."
        )

    if grant.revoked_at is not None:
        raise HTTPException(status_code=409, detail="Grant is already revoked.")

    grant.revoked_at = datetime.now(UTC)
    await db.commit()
