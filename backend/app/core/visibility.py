"""
Field-level visibility filtering for DailyRecord responses.

Private fields: day_load (on DailyRecord), blocker_text (on each TaskEntry).
These are stripped when the requester is not the record owner, the owner's
active leader, or an admin.

WebSocket payloads MUST reuse this module — do not implement a separate
visibility check for WS events.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.absence import SharingGrant
from app.db.models.team import TeamMembership

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.schemas.daily_record import DailyRecordResponse


async def is_record_fully_visible(
    record_user_id: uuid.UUID,
    requester: User,
    db: AsyncSession,
) -> bool:
    """
    Return True if the requester may see private fields for a record owned by
    record_user_id.

    Privileged when requester is:
    - The record owner
    - An admin
    - The current active leader of the record owner's team (time-scoped via
      TeamMembership.left_at)
    - A leader with an active SharingGrant for the team the record owner
      belongs to (cross-team read access, non-transitive — grantee cannot
      re-share).
    """
    if requester.id == record_user_id:
        return True
    if requester.is_admin:
        return True
    if requester.is_leader:
        # Find record owner's current team
        r_owner = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == record_user_id,
                TeamMembership.left_at.is_(None),
            )
        )
        owner_mem = r_owner.scalar_one_or_none()
        if owner_mem is None:
            return False

        # Check if leader is in the same team
        r_leader = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == requester.id,
                TeamMembership.team_id == owner_mem.team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        if r_leader.scalar_one_or_none() is not None:
            return True

        # Check for an active SharingGrant: another leader granted this
        # requester access to the record owner's team.
        r_grant = await db.execute(
            select(SharingGrant).where(
                SharingGrant.granted_to_leader_id == requester.id,
                SharingGrant.team_id == owner_mem.team_id,
                SharingGrant.revoked_at.is_(None),
            )
        )
        return r_grant.scalar_one_or_none() is not None

    return False


def apply_visibility_filter(
    record: DailyRecordResponse,
    *,
    visible: bool,
) -> DailyRecordResponse:
    """
    Return a copy of the DailyRecordResponse with private fields cleared
    when visible=False.

    Private fields nulled:
    - DailyRecordResponse.day_load → None
    - TaskEntryResponse.blocker_text → None for all task entries
    """
    if visible:
        return record
    filtered_tasks = [
        te.model_copy(update={"blocker_text": None}) for te in record.task_entries
    ]
    return record.model_copy(update={"day_load": None, "task_entries": filtered_tasks})
