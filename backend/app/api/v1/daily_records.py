from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_active_user
from app.core.edit_window import check_edit_window
from app.core.validators import validate_self_assessment_tags
from app.core.visibility import apply_visibility_filter, is_record_fully_visible
from app.db.engine import get_db
from app.db.models.absence import Absence, UnlockGrant
from app.db.models.daily_record import DailyRecord
from app.db.models.task_entry import TaskEntry, TaskEntrySelfAssessmentTag
from app.db.models.team import TeamMembership
from app.db.models.user import User
from app.db.schemas.daily_record import (
    DailyRecordCreate,
    DailyRecordResponse,
    DailyRecordUpdate,
    SelfAssessmentTagRefResponse,
    TaskEntryResponse,
    UnlockGrantCreate,
    UnlockGrantResponse,
)

router = APIRouter(tags=["daily-records"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_task_entry_response(
    te: TaskEntry, db: AsyncSession
) -> TaskEntryResponse:
    tags_result = await db.execute(
        select(TaskEntrySelfAssessmentTag).where(
            TaskEntrySelfAssessmentTag.task_entry_id == te.id
        )
    )
    tags = [
        SelfAssessmentTagRefResponse(
            self_assessment_tag_id=t.self_assessment_tag_id,
            is_primary=t.is_primary,
        )
        for t in tags_result.scalars().all()
    ]
    return TaskEntryResponse(
        id=te.id,
        daily_record_id=te.daily_record_id,
        category_id=te.category_id,
        sub_type_id=te.sub_type_id,
        project_id=te.project_id,
        task_description=te.task_description,
        effort=te.effort,
        status=te.status,
        blocker_type_id=te.blocker_type_id,
        blocker_text=te.blocker_text,
        carried_from_id=te.carried_from_id,
        sort_order=te.sort_order,
        self_assessment_tags=tags,
    )


async def _build_record_response(
    record: DailyRecord, db: AsyncSession
) -> DailyRecordResponse:
    te_result = await db.execute(
        select(TaskEntry)
        .where(TaskEntry.daily_record_id == record.id)
        .order_by(TaskEntry.sort_order)
    )
    task_entries = [
        await _build_task_entry_response(te, db) for te in te_result.scalars().all()
    ]
    return DailyRecordResponse(
        id=record.id,
        user_id=record.user_id,
        record_date=record.record_date,
        day_load=record.day_load,
        day_note=record.day_note,
        form_opened_at=record.form_opened_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        task_entries=task_entries,
    )


async def _check_edit_window_or_unlock(
    user_id: uuid.UUID,
    record_date,
    form_opened_at: datetime,
    db: AsyncSession,
) -> None:
    """Raises 423 if edit window is closed and no active unlock grant exists."""
    allowed, reason = check_edit_window(record_date, form_opened_at)
    if not allowed:
        grant_result = await db.execute(
            select(UnlockGrant).where(
                UnlockGrant.user_id == user_id,
                UnlockGrant.record_date == record_date,
                UnlockGrant.revoked_at.is_(None),
            )
        )
        if grant_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=423, detail=reason)


async def _create_task_entries(
    record_id: uuid.UUID,
    task_entries_data,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Create TaskEntry rows + tag junction rows for a DailyRecord."""
    for te_data in task_entries_data:
        # Validate carried_from_id belongs to same user
        if te_data.carried_from_id is not None:
            source_te_result = await db.execute(
                select(TaskEntry).where(TaskEntry.id == te_data.carried_from_id)
            )
            source_te = source_te_result.scalar_one_or_none()
            if source_te is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"carried_from_id {te_data.carried_from_id} not found.",
                )
            # Verify ownership via the source task's daily record
            source_dr_result = await db.execute(
                select(DailyRecord).where(DailyRecord.id == source_te.daily_record_id)
            )
            source_dr = source_dr_result.scalar_one_or_none()
            if source_dr is None or source_dr.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="carried_from_id must refer to a task entry owned by the current user.",
                )

        te = TaskEntry(
            daily_record_id=record_id,
            category_id=te_data.category_id,
            sub_type_id=te_data.sub_type_id,
            project_id=te_data.project_id,
            task_description=te_data.task_description,
            effort=te_data.effort,
            status=te_data.status,
            blocker_type_id=te_data.blocker_type_id,
            blocker_text=te_data.blocker_text,
            carried_from_id=te_data.carried_from_id,
            sort_order=te_data.sort_order,
        )
        db.add(te)
        await db.flush()

        for tag_data in te_data.self_assessment_tags:
            db.add(
                TaskEntrySelfAssessmentTag(
                    task_entry_id=te.id,
                    self_assessment_tag_id=tag_data.self_assessment_tag_id,
                    is_primary=tag_data.is_primary,
                )
            )


# ---------------------------------------------------------------------------
# Daily Record endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/daily-records",
    status_code=status.HTTP_201_CREATED,
    response_model=DailyRecordResponse,
)
async def create_daily_record(
    body: DailyRecordCreate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Check mutual exclusion with Absence
    absence_check = await db.execute(
        select(Absence).where(
            Absence.user_id == current_user.id,
            Absence.record_date == body.record_date,
        )
    )
    if absence_check.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An absence is already recorded for this date. Remove it first.",
        )

    # Check for duplicate daily record
    dup_check = await db.execute(
        select(DailyRecord).where(
            DailyRecord.user_id == current_user.id,
            DailyRecord.record_date == body.record_date,
        )
    )
    if dup_check.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A daily record already exists for this date.",
        )

    # Check edit window
    await _check_edit_window_or_unlock(
        current_user.id, body.record_date, body.form_opened_at, db
    )

    # Validate self-assessment tags
    if body.task_entries:
        try:
            validate_self_assessment_tags(body.task_entries)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    record = DailyRecord(
        user_id=current_user.id,
        record_date=body.record_date,
        day_load=body.day_load,
        day_note=body.day_note,
        form_opened_at=body.form_opened_at,
    )
    db.add(record)
    await db.flush()

    await _create_task_entries(record.id, body.task_entries, current_user.id, db)

    await db.commit()
    await db.refresh(record)
    return await _build_record_response(record, db)


@router.get("/daily-records/carry-over", response_model=list[TaskEntryResponse])
async def get_carry_over_tasks(
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return running/blocked tasks from the most recent daily record."""
    latest_result = await db.execute(
        select(DailyRecord)
        .where(DailyRecord.user_id == current_user.id)
        .order_by(DailyRecord.record_date.desc())
        .limit(1)
    )
    latest_record = latest_result.scalar_one_or_none()
    if latest_record is None:
        return []

    te_result = await db.execute(
        select(TaskEntry).where(
            TaskEntry.daily_record_id == latest_record.id,
            TaskEntry.status.in_(["running", "blocked"]),
        )
    )
    return [
        await _build_task_entry_response(te, db) for te in te_result.scalars().all()
    ]


@router.get("/daily-records", response_model=list[DailyRecordResponse])
async def list_daily_records(
    user_id: uuid.UUID | None = Query(default=None),
    date: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_user_id = user_id if user_id is not None else current_user.id

    # Authorization check
    if target_user_id != current_user.id:
        if current_user.is_admin:
            pass  # admin can query anyone
        elif current_user.is_leader:
            # Leader can query their team members
            leader_team_result = await db.execute(
                select(TeamMembership).where(
                    TeamMembership.user_id == current_user.id,
                    TeamMembership.left_at.is_(None),
                )
            )
            leader_team = leader_team_result.scalar_one_or_none()
            if leader_team is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )
            member_check = await db.execute(
                select(TeamMembership).where(
                    TeamMembership.user_id == target_user_id,
                    TeamMembership.team_id == leader_team.team_id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if member_check.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: user is not in your team",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    stmt = select(DailyRecord).where(DailyRecord.user_id == target_user_id)

    if date is not None:
        from datetime import date as date_type

        parsed = date_type.fromisoformat(date)
        stmt = stmt.where(DailyRecord.record_date == parsed)
    else:
        if start_date is not None:
            from datetime import date as date_type

            stmt = stmt.where(
                DailyRecord.record_date >= date_type.fromisoformat(start_date)
            )
        if end_date is not None:
            from datetime import date as date_type

            stmt = stmt.where(
                DailyRecord.record_date <= date_type.fromisoformat(end_date)
            )

    stmt = stmt.order_by(DailyRecord.record_date.desc())
    result = await db.execute(stmt)
    records = result.scalars().all()

    responses = []
    for r in records:
        resp = await _build_record_response(r, db)
        visible = await is_record_fully_visible(r.user_id, current_user, db)
        responses.append(apply_visibility_filter(resp, visible=visible))
    return responses


@router.put("/daily-records/{record_id}", response_model=DailyRecordResponse)
async def update_daily_record(
    record_id: uuid.UUID,
    body: DailyRecordUpdate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DailyRecord).where(DailyRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )

    # Ownership check
    if record.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # Check edit window
    await _check_edit_window_or_unlock(
        record.user_id, record.record_date, body.form_opened_at, db
    )

    # If updating task_entries, validate carried_from_id immutability and tags
    if body.task_entries is not None:
        # Load existing task entries to check carried_from_id immutability
        existing_te_result = await db.execute(
            select(TaskEntry).where(TaskEntry.daily_record_id == record.id)
        )
        existing_entries = existing_te_result.scalars().all()

        existing_carried_ids = {
            te.carried_from_id
            for te in existing_entries
            if te.carried_from_id is not None
        }
        new_carried_ids = {
            te_data.carried_from_id
            for te_data in body.task_entries
            if te_data.carried_from_id is not None
        }

        # If any previously-set carried_from_id is missing or changed in the new list → reject
        if existing_carried_ids and existing_carried_ids != new_carried_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="carried_from_id is immutable after creation. "
                "The set of carried_from_id values cannot be changed on update.",
            )

        # Validate self-assessment tags
        try:
            validate_self_assessment_tags(body.task_entries)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Full replacement: delete existing task entries and their tags
        for te in existing_entries:
            tags_result = await db.execute(
                select(TaskEntrySelfAssessmentTag).where(
                    TaskEntrySelfAssessmentTag.task_entry_id == te.id
                )
            )
            for tag in tags_result.scalars().all():
                await db.delete(tag)
            await db.delete(te)
        await db.flush()

        await _create_task_entries(record.id, body.task_entries, record.user_id, db)

    # Update scalar fields
    if body.day_load is not None:
        record.day_load = body.day_load
    if body.day_note is not None:
        record.day_note = body.day_note
    record.form_opened_at = body.form_opened_at

    await db.commit()
    await db.refresh(record)
    return await _build_record_response(record, db)


# ---------------------------------------------------------------------------
# Unlock Grant endpoints
# ---------------------------------------------------------------------------

unlock_router = APIRouter(tags=["unlock-grants"])


@unlock_router.post(
    "/unlock-grants",
    status_code=status.HTTP_201_CREATED,
    response_model=UnlockGrantResponse,
)
async def create_unlock_grant(
    body: UnlockGrantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_leader and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leader or admin access required",
        )

    # Leader must have target user in their team
    if not current_user.is_admin:
        leader_team_result = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.left_at.is_(None),
            )
        )
        leader_team = leader_team_result.scalar_one_or_none()
        if leader_team is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Leader is not in any active team",
            )
        member_check = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == body.user_id,
                TeamMembership.team_id == leader_team.team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        if member_check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Target user is not in your team",
            )

    # Application-level uniqueness: at most one active unlock per (user, date)
    existing = await db.execute(
        select(UnlockGrant).where(
            UnlockGrant.user_id == body.user_id,
            UnlockGrant.record_date == body.record_date,
            UnlockGrant.revoked_at.is_(None),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active unlock grant already exists for this user and date.",
        )

    grant = UnlockGrant(
        user_id=body.user_id,
        record_date=body.record_date,
        granted_by=current_user.id,
        granted_at=datetime.now(UTC),
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return UnlockGrantResponse.model_validate(grant)


@unlock_router.delete("/unlock-grants/{grant_id}", status_code=status.HTTP_200_OK)
async def revoke_unlock_grant(
    grant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_leader and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leader or admin access required",
        )

    result = await db.execute(select(UnlockGrant).where(UnlockGrant.id == grant_id))
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unlock grant not found"
        )

    grant.revoked_at = datetime.now(UTC)
    await db.commit()
    return {"message": "Unlock grant revoked"}


@unlock_router.get("/unlock-grants", response_model=list[UnlockGrantResponse])
async def list_unlock_grants(
    user_id: uuid.UUID | None = Query(default=None),
    record_date: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_leader and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leader or admin access required",
        )

    stmt = select(UnlockGrant).where(UnlockGrant.revoked_at.is_(None))

    if not current_user.is_admin:
        # Leader: scope to own team members
        leader_team_result = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.left_at.is_(None),
            )
        )
        leader_team = leader_team_result.scalar_one_or_none()
        if leader_team is not None:
            team_member_ids_result = await db.execute(
                select(TeamMembership.user_id).where(
                    TeamMembership.team_id == leader_team.team_id,
                    TeamMembership.left_at.is_(None),
                )
            )
            team_member_ids = [row[0] for row in team_member_ids_result.all()]
            stmt = stmt.where(UnlockGrant.user_id.in_(team_member_ids))

    if user_id is not None:
        stmt = stmt.where(UnlockGrant.user_id == user_id)
    if record_date is not None:
        from datetime import date as date_type

        stmt = stmt.where(
            UnlockGrant.record_date == date_type.fromisoformat(record_date)
        )

    result = await db.execute(stmt)
    return [UnlockGrantResponse.model_validate(g) for g in result.scalars().all()]
