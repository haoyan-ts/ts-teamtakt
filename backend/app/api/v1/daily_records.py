from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_active_user
from app.core.edit_window import check_edit_window
from app.core.validators import validate_self_assessment_tags
from app.core.visibility import apply_visibility_filter, is_record_fully_visible
from app.core.working_days import count_working_days
from app.db.engine import get_db
from app.db.models.daily_record import DailyRecord
from app.db.models.grants import UnlockGrant
from app.db.models.task import DailyWorkLog, DailyWorkLogSelfAssessmentTag, Task
from app.db.models.team import TeamMembership, TeamSettings
from app.db.models.user import User
from app.db.schemas.daily_record import (
    DailyEffortBreakdownResponse,
    DailyRecordCreate,
    DailyRecordResponse,
    DailyRecordUpdate,
    EnergyTypeEffort,
    UnlockGrantCreate,
    UnlockGrantResponse,
)
from app.db.schemas.task import DailyWorkLogResponse, SelfAssessmentTagRefResponse
from app.services.notification import NotificationService

router = APIRouter(tags=["daily-records"])
unlock_router = APIRouter(tags=["daily-records"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _notify_blocker_aging(
    user_id: uuid.UUID,
    record_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Check running/blocked tasks in this record against team threshold; notify."""
    # Find DailyWorkLogs in this record whose linked Task is running or blocked
    r = await db.execute(
        select(DailyWorkLog, Task)
        .join(Task, DailyWorkLog.task_id == Task.id)
        .where(
            DailyWorkLog.daily_record_id == record_id,
            Task.status.in_(["running", "blocked"]),
        )
    )
    rows = r.all()
    if not rows:
        return

    membership = await db.scalar(
        select(TeamMembership).where(
            TeamMembership.user_id == user_id,
            TeamMembership.left_at.is_(None),
        )
    )
    if membership is None:
        return

    settings = await db.scalar(
        select(TeamSettings).where(TeamSettings.team_id == membership.team_id)
    )
    threshold = settings.carryover_aging_days if settings else 5

    today = datetime.now(UTC).date()
    aging: list[tuple[Task, int]] = []
    for _log, task in rows:
        age = count_working_days(task.created_at.date(), today)
        if age >= threshold:
            aging.append((task, age))

    if not aging:
        return

    svc = NotificationService(db)
    max_age = max(age for _, age in aging)
    count = len(aging)

    await svc.send(
        user_id=user_id,
        trigger_type="blocker_aging",
        title=f"{count} task(s) aging \u2265 {threshold} working day(s)",
        body=f"Your oldest running/blocked task is {max_age} working day(s) old.",
        data={"task_ids": [str(t.id) for t, _ in aging], "max_age": max_age},
    )

    leader_r = await db.execute(
        select(User)
        .join(TeamMembership, User.id == TeamMembership.user_id)
        .where(
            TeamMembership.team_id == membership.team_id,
            TeamMembership.left_at.is_(None),
            User.is_leader.is_(True),
            User.id != user_id,
        )
    )
    leaders = leader_r.scalars().all()
    member = await db.scalar(select(User).where(User.id == user_id))
    member_name = member.display_name if member else "A team member"
    for leader in leaders:
        await svc.send(
            user_id=leader.id,
            trigger_type="team_member_blocked",
            title=f"{member_name} has {count} aging task(s)",
            body=f"Oldest task is {max_age} working day(s) old.",
            data={
                "member_id": str(user_id),
                "task_ids": [str(t.id) for t, _ in aging],
                "max_age": max_age,
            },
        )


async def _build_work_log_response(
    log: DailyWorkLog, db: AsyncSession
) -> DailyWorkLogResponse:
    tags_r = await db.execute(
        select(DailyWorkLogSelfAssessmentTag).where(
            DailyWorkLogSelfAssessmentTag.daily_work_log_id == log.id
        )
    )
    tags = [
        SelfAssessmentTagRefResponse(
            self_assessment_tag_id=t.self_assessment_tag_id,
            is_primary=t.is_primary,
        )
        for t in tags_r.scalars().all()
    ]
    return DailyWorkLogResponse(
        id=log.id,
        task_id=log.task_id,
        daily_record_id=log.daily_record_id,
        effort=log.effort,
        energy_type=log.energy_type,
        insight=log.insight,
        blocker_type_id=log.blocker_type_id,
        blocker_text=log.blocker_text,
        sort_order=log.sort_order,
        self_assessment_tags=tags,
    )


async def _build_record_response(
    record: DailyRecord, db: AsyncSession
) -> DailyRecordResponse:
    logs_r = await db.execute(
        select(DailyWorkLog)
        .where(DailyWorkLog.daily_record_id == record.id)
        .order_by(DailyWorkLog.sort_order)
    )
    daily_work_logs = [
        await _build_work_log_response(log, db) for log in logs_r.scalars().all()
    ]
    return DailyRecordResponse(
        id=record.id,
        user_id=record.user_id,
        record_date=record.record_date,
        day_load=record.day_load,
        day_insight=record.day_insight,
        form_opened_at=record.form_opened_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        daily_work_logs=daily_work_logs,
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
        grant = await db.scalar(
            select(UnlockGrant).where(
                UnlockGrant.user_id == user_id,
                UnlockGrant.record_date == record_date,
                UnlockGrant.revoked_at.is_(None),
            )
        )
        if grant is None:
            raise HTTPException(status_code=423, detail=reason)


async def _create_daily_work_logs(
    record_id: uuid.UUID,
    logs_data,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Create DailyWorkLog rows + tag junction rows for a DailyRecord."""
    for log_data in logs_data:
        # Verify the task exists and belongs to this user
        task = await db.scalar(
            select(Task).where(
                Task.id == log_data.task_id,
                Task.assignee_id == user_id,
            )
        )
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task {log_data.task_id} not found or does not belong to this user.",
            )

        # Enforce UNIQUE(task_id, daily_record_id) at app level
        dup = await db.scalar(
            select(DailyWorkLog).where(
                DailyWorkLog.task_id == log_data.task_id,
                DailyWorkLog.daily_record_id == record_id,
            )
        )
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A work log for task {log_data.task_id} already exists in this record.",
            )

        log = DailyWorkLog(
            daily_record_id=record_id,
            task_id=log_data.task_id,
            effort=log_data.effort,
            energy_type=log_data.energy_type,
            insight=log_data.insight,
            blocker_type_id=log_data.blocker_type_id,
            blocker_text=log_data.blocker_text,
            sort_order=log_data.sort_order,
        )
        db.add(log)
        await db.flush()

        for tag_data in log_data.self_assessment_tags:
            db.add(
                DailyWorkLogSelfAssessmentTag(
                    daily_work_log_id=log.id,
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
    # Check for duplicate daily record
    dup_check = await db.scalar(
        select(DailyRecord).where(
            DailyRecord.user_id == current_user.id,
            DailyRecord.record_date == body.record_date,
        )
    )
    if dup_check is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A daily record already exists for this date.",
        )

    await _check_edit_window_or_unlock(
        current_user.id, body.record_date, body.form_opened_at, db
    )

    if body.daily_work_logs:
        try:
            validate_self_assessment_tags(body.daily_work_logs)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    record = DailyRecord(
        user_id=current_user.id,
        record_date=body.record_date,
        day_load=body.day_load,
        day_insight=body.day_insight,
        form_opened_at=body.form_opened_at,
    )
    db.add(record)
    await db.flush()

    await _create_daily_work_logs(record.id, body.daily_work_logs, current_user.id, db)

    await db.commit()
    await db.refresh(record)

    await _notify_blocker_aging(current_user.id, record.id, db)
    await db.commit()

    return await _build_record_response(record, db)


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

    if target_user_id != current_user.id:
        if current_user.is_admin:
            pass
        elif current_user.is_leader:
            leader_team = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == current_user.id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if leader_team is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )
            member_check = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == target_user_id,
                    TeamMembership.team_id == leader_team.team_id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if member_check is None:
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


@router.get("/daily-records/breakdown", response_model=DailyEffortBreakdownResponse)
async def get_effort_breakdown(
    date: str = Query(..., description="ISO date string, e.g. 2026-04-20"),
    user_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return daily effort totals broken down by energy_type for a given user and date.
    battery_pct (= day_load) is included only when the requester has visibility rights.
    """
    from datetime import date as date_type

    parsed_date = date_type.fromisoformat(date)
    target_user_id = user_id if user_id is not None else current_user.id

    if target_user_id != current_user.id:
        if current_user.is_admin:
            pass
        elif current_user.is_leader:
            leader_membership = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == current_user.id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if leader_membership is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )
            member_membership = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == target_user_id,
                    TeamMembership.team_id == leader_membership.team_id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if member_membership is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: user is not in your team",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    record = await db.scalar(
        select(DailyRecord).where(
            DailyRecord.user_id == target_user_id,
            DailyRecord.record_date == parsed_date,
        )
    )
    if record is None:
        return DailyEffortBreakdownResponse(
            user_id=target_user_id,
            record_date=parsed_date,
            total_effort=0,
            by_energy_type=[],
            battery_pct=None,
        )

    logs_r = await db.execute(
        select(DailyWorkLog).where(DailyWorkLog.daily_record_id == record.id)
    )
    logs = logs_r.scalars().all()

    effort_map: dict[str | None, int] = {}
    for log in logs:
        key = str(log.energy_type) if log.energy_type is not None else None
        effort_map[key] = effort_map.get(key, 0) + log.effort

    by_energy_type = [
        EnergyTypeEffort(energy_type=k, effort=v)
        for k, v in sorted(effort_map.items(), key=lambda x: x[0] or "")
    ]

    visible = await is_record_fully_visible(target_user_id, current_user, db)
    battery_pct = record.day_load if visible else None

    return DailyEffortBreakdownResponse(
        user_id=target_user_id,
        record_date=parsed_date,
        total_effort=sum(effort_map.values()),
        by_energy_type=by_energy_type,
        battery_pct=battery_pct,
    )


@router.get("/daily-records/{record_id}", response_model=DailyRecordResponse)
async def get_daily_record(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DailyRecord).where(DailyRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )

    if record.user_id != current_user.id:
        if current_user.is_admin:
            pass
        elif current_user.is_leader:
            leader_team = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == current_user.id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if leader_team is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )
            member_check = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == record.user_id,
                    TeamMembership.team_id == leader_team.team_id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if member_check is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: user is not in your team",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    resp = await _build_record_response(record, db)
    visible = await is_record_fully_visible(record.user_id, current_user, db)
    return apply_visibility_filter(resp, visible=visible)


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

    if record.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    await _check_edit_window_or_unlock(
        record.user_id, record.record_date, body.form_opened_at, db
    )

    if body.daily_work_logs is not None:
        try:
            validate_self_assessment_tags(body.daily_work_logs)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Full replacement: delete tags first (respects FK), then work logs
        existing_logs_r = await db.execute(
            select(DailyWorkLog).where(DailyWorkLog.daily_record_id == record.id)
        )
        existing_log_ids = [log.id for log in existing_logs_r.scalars().all()]
        if existing_log_ids:
            await db.execute(
                sql_delete(DailyWorkLogSelfAssessmentTag).where(
                    DailyWorkLogSelfAssessmentTag.daily_work_log_id.in_(
                        existing_log_ids
                    )
                )
            )
            await db.flush()
            await db.execute(
                sql_delete(DailyWorkLog).where(
                    DailyWorkLog.daily_record_id == record.id
                )
            )
            await db.flush()

        await _create_daily_work_logs(
            record.id, body.daily_work_logs, record.user_id, db
        )

    if body.day_load is not None:
        record.day_load = body.day_load
    if body.day_insight is not None:
        record.day_insight = body.day_insight
    record.form_opened_at = body.form_opened_at

    await db.commit()
    await db.refresh(record)

    await _notify_blocker_aging(record.user_id, record.id, db)
    await db.commit()

    return await _build_record_response(record, db)


# ---------------------------------------------------------------------------
# Unlock grant endpoints
# ---------------------------------------------------------------------------


@unlock_router.post(
    "/unlock-grants",
    status_code=status.HTTP_201_CREATED,
    response_model=UnlockGrantResponse,
)
async def create_unlock_grant(
    body: UnlockGrantCreate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_leader and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Leader or admin required"
        )
    grant = UnlockGrant(
        user_id=body.user_id,
        record_date=body.record_date,
        granted_by=current_user.id,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


@unlock_router.get("/unlock-grants", response_model=list[UnlockGrantResponse])
async def list_unlock_grants(
    user_id: uuid.UUID | None = Query(default=None),
    record_date: date | None = Query(default=None),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_leader and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Leader or admin required"
        )
    stmt = select(UnlockGrant)
    if user_id is not None:
        stmt = stmt.where(UnlockGrant.user_id == user_id)
    if record_date is not None:
        stmt = stmt.where(UnlockGrant.record_date == record_date)
    r = await db.execute(stmt)
    return r.scalars().all()


@unlock_router.delete(
    "/unlock-grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_unlock_grant(
    grant_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_leader and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Leader or admin required"
        )
    grant = await db.scalar(select(UnlockGrant).where(UnlockGrant.id == grant_id))
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found"
        )
    grant.revoked_at = datetime.now(UTC)
    await db.commit()
