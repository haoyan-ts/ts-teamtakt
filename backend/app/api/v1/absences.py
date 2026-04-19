from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_active_user, require_leader
from app.core.edit_window import check_edit_window
from app.db.engine import get_db
from app.db.models.absence import Absence, UnlockGrant
from app.db.models.absence import AbsenceType as AbsenceTypeEnum
from app.db.models.daily_record import DailyRecord
from app.db.models.team import TeamMembership
from app.db.models.user import User
from app.db.schemas.absence import AbsenceCreate, AbsenceResponse, AbsenceUpdate

router = APIRouter(tags=["absences"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _check_edit_window_or_unlock(
    user_id: uuid.UUID,
    record_date: date,
    form_opened_at: datetime,
    db: AsyncSession,
) -> None:
    """Raises 423 if the edit window is closed and no active unlock grant exists."""
    allowed, reason = check_edit_window(record_date, form_opened_at)
    if not allowed:
        grant_r = await db.execute(
            select(UnlockGrant).where(
                UnlockGrant.user_id == user_id,
                UnlockGrant.record_date == record_date,
                UnlockGrant.revoked_at.is_(None),
            )
        )
        if grant_r.scalar_one_or_none() is None:
            raise HTTPException(status_code=423, detail=reason)


def _working_days_in_range(start: date, end: date) -> list[date]:
    """
    Return Mon–Fri dates between start and end inclusive.

    Phase G extends this to exclude holidays from the holiday_calendar table.
    """
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            days.append(current)
        current += timedelta(days=1)
    return days


async def _assert_leader_access_to_user(
    requester: User,
    target_user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Raise 403 unless requester is admin or the active leader of target user's team."""
    if requester.is_admin:
        return
    if requester.is_leader:
        lm_r = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == requester.id,
                TeamMembership.left_at.is_(None),
            )
        )
        lm = lm_r.scalar_one_or_none()
        if lm is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        mc = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == target_user_id,
                TeamMembership.team_id == lm.team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        if mc.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: user is not in your team",
            )
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/absences", status_code=status.HTTP_201_CREATED, response_model=AbsenceResponse
)
async def create_absence(
    body: AbsenceCreate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an absence for the current user on a given date."""
    # Edit window check (same formula as DailyRecord)
    await _check_edit_window_or_unlock(
        current_user.id, body.record_date, body.form_opened_at, db
    )

    # Mutual exclusion: reject if a DailyRecord already exists for this date
    dr_check = await db.execute(
        select(DailyRecord).where(
            DailyRecord.user_id == current_user.id,
            DailyRecord.record_date == body.record_date,
        )
    )
    if dr_check.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A daily record already exists for this date. Remove it first.",
        )

    # Duplicate absence check
    dup_check = await db.execute(
        select(Absence).where(
            Absence.user_id == current_user.id,
            Absence.record_date == body.record_date,
        )
    )
    if dup_check.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An absence is already recorded for this date.",
        )

    absence = Absence(
        user_id=current_user.id,
        record_date=body.record_date,
        absence_type=body.absence_type,
        note=body.note,
    )
    db.add(absence)
    await db.commit()
    await db.refresh(absence)
    return absence


@router.get("/absences/{absence_id}", response_model=AbsenceResponse)
async def get_absence(
    absence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Absence).where(Absence.id == absence_id))
    absence = result.scalar_one_or_none()
    if absence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Absence not found"
        )

    if absence.user_id != current_user.id:
        await _assert_leader_access_to_user(current_user, absence.user_id, db)

    return absence


@router.get("/absences", response_model=list[AbsenceResponse])
async def list_absences(
    user_id: uuid.UUID | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List absences. Defaults to own records; leaders/admins may query team members."""
    target_user_id = user_id if user_id is not None else current_user.id

    if target_user_id != current_user.id:
        await _assert_leader_access_to_user(current_user, target_user_id, db)

    stmt = select(Absence).where(Absence.user_id == target_user_id)
    if start_date:
        stmt = stmt.where(Absence.record_date >= date.fromisoformat(start_date))
    if end_date:
        stmt = stmt.where(Absence.record_date <= date.fromisoformat(end_date))
    stmt = stmt.order_by(Absence.record_date.desc())

    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/absences/{absence_id}", response_model=AbsenceResponse)
async def update_absence(
    absence_id: uuid.UUID,
    body: AbsenceUpdate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Absence).where(Absence.id == absence_id))
    absence = result.scalar_one_or_none()
    if absence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Absence not found"
        )
    if absence.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    await _check_edit_window_or_unlock(
        current_user.id, absence.record_date, body.form_opened_at, db
    )

    if body.absence_type is not None:
        absence.absence_type = AbsenceTypeEnum(body.absence_type)
    if body.note is not None:
        absence.note = body.note

    await db.commit()
    await db.refresh(absence)
    return absence


@router.delete("/absences/{absence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_absence(
    absence_id: uuid.UUID,
    form_opened_at: datetime = Query(
        ..., description="form_opened_at for edit window check"
    ),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Absence).where(Absence.id == absence_id))
    absence = result.scalar_one_or_none()
    if absence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Absence not found"
        )
    if absence.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    await _check_edit_window_or_unlock(
        current_user.id, absence.record_date, form_opened_at, db
    )

    await db.delete(absence)
    await db.commit()


@router.get("/missing-days", response_model=list[date])
async def get_missing_days(
    user_id: uuid.UUID | None = Query(default=None),
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return working days (Mon–Fri) in the given date range where the user has
    neither a DailyRecord nor an Absence.
    """
    target_user_id = user_id if user_id is not None else current_user.id

    if target_user_id != current_user.id:
        await _assert_leader_access_to_user(current_user, target_user_id, db)

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    working_days = _working_days_in_range(start, end)

    dr_r = await db.execute(
        select(DailyRecord.record_date).where(
            DailyRecord.user_id == target_user_id,
            DailyRecord.record_date >= start,
            DailyRecord.record_date <= end,
        )
    )
    reported_dates = {row[0] for row in dr_r.all()}

    ab_r = await db.execute(
        select(Absence.record_date).where(
            Absence.user_id == target_user_id,
            Absence.record_date >= start,
            Absence.record_date <= end,
        )
    )
    absent_dates = {row[0] for row in ab_r.all()}

    return [
        d for d in working_days if d not in reported_dates and d not in absent_dates
    ]


@router.get("/teams/{team_id}/missing-days")
async def get_team_missing_days(
    team_id: uuid.UUID,
    week: str = Query(
        ..., description="ISO date of the Monday of the target week (YYYY-MM-DD)"
    ),
    current_user: User = Depends(require_leader),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[date]]:
    """
    Return per-member missing days for a given week.
    Leader must belong to the team (admins exempt).
    """
    if not current_user.is_admin:
        lm_r = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.team_id == team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        if lm_r.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: not a member of this team",
            )

    week_start = date.fromisoformat(week)
    week_end = week_start + timedelta(days=4)  # Mon → Fri
    working_days = _working_days_in_range(week_start, week_end)

    members_r = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    member_ids = [m.user_id for m in members_r.scalars().all()]

    result: dict[str, list[date]] = {}
    for uid in member_ids:
        dr_r = await db.execute(
            select(DailyRecord.record_date).where(
                DailyRecord.user_id == uid,
                DailyRecord.record_date >= week_start,
                DailyRecord.record_date <= week_end,
            )
        )
        reported = {row[0] for row in dr_r.all()}

        ab_r = await db.execute(
            select(Absence.record_date).where(
                Absence.user_id == uid,
                Absence.record_date >= week_start,
                Absence.record_date <= week_end,
            )
        )
        absent = {row[0] for row in ab_r.all()}

        missing = [d for d in working_days if d not in reported and d not in absent]
        if missing:
            result[str(uid)] = missing

    return result
