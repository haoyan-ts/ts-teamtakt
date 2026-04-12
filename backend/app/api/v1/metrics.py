"""
Leader Metrics API — 6 endpoints under /teams/{id}/metrics/*

Carry-over aging invariant (updated):
  aging = calendar working-days from Task.created_at.date() to today.
  No chain traversal needed — Task is the stable identity.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.working_days import count_working_days
from app.db.engine import get_db
from app.db.models.category import BlockerType, Category
from app.db.models.daily_record import DailyRecord
from app.db.models.project import Project
from app.db.models.task import DailyWorkLog, Task
from app.db.models.team import TeamMembership, TeamSettings
from app.db.models.user import User
from app.db.schemas.metrics import (
    BlockerByType,
    BlockerSummary,
    CarryoverAgingEntry,
    FragmentationEntry,
    MemberBalance,
    MemberEffort,
    OverloadEntry,
    ProjectEffortEntry,
    RecurringBlocker,
    TeamBalance,
)

router = APIRouter(prefix="/teams", tags=["metrics"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _get_active_members(
    team_id: uuid.UUID, db: AsyncSession
) -> dict[uuid.UUID, str]:
    """Return {user_id: display_name} for active team members."""
    r = await db.execute(
        select(User.id, User.display_name)
        .join(TeamMembership, User.id == TeamMembership.user_id)
        .where(
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    return {row.id: row.display_name for row in r.all()}


async def _get_settings(team_id: uuid.UUID, db: AsyncSession) -> TeamSettings:
    r = await db.execute(select(TeamSettings).where(TeamSettings.team_id == team_id))
    s = r.scalar_one_or_none()
    if s is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team settings not found"
        )
    return s


# ---------------------------------------------------------------------------
# 1. Overload Detection
# ---------------------------------------------------------------------------


@router.get("/{team_id}/metrics/overload", response_model=list[OverloadEntry])
async def overload_detection(
    team_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    members = await _get_active_members(team_id, db)
    settings = await _get_settings(team_id, db)

    if not members:
        return []

    r = await db.execute(
        select(DailyRecord.user_id, DailyRecord.record_date, DailyRecord.day_load)
        .where(
            DailyRecord.user_id.in_(members.keys()),
            DailyRecord.record_date >= start_date,
            DailyRecord.record_date <= end_date,
        )
        .order_by(DailyRecord.user_id, DailyRecord.record_date)
    )
    rows = r.all()

    by_user: dict[uuid.UUID, list[tuple[date, int]]] = defaultdict(list)
    for row in rows:
        by_user[row.user_id].append((row.record_date, row.day_load))

    results: list[OverloadEntry] = []
    threshold = settings.overload_load_threshold
    min_streak = settings.overload_streak_days

    for uid, records in by_user.items():
        streak_start = None
        streak_end = None
        max_load = 0
        for d, load in records:
            if load >= threshold:
                if streak_start is None:
                    streak_start = d
                streak_end = d
                max_load = max(max_load, load)
            else:
                if streak_start and streak_end:
                    streak_len = count_working_days(streak_start, streak_end)
                    if streak_len >= min_streak:
                        results.append(
                            OverloadEntry(
                                user_id=uid,
                                display_name=members[uid],
                                streak_start=streak_start,
                                streak_end=streak_end,
                                max_load=max_load,
                            )
                        )
                streak_start = None
                streak_end = None
                max_load = 0

        if streak_start and streak_end:
            streak_len = count_working_days(streak_start, streak_end)
            if streak_len >= min_streak:
                results.append(
                    OverloadEntry(
                        user_id=uid,
                        display_name=members[uid],
                        streak_start=streak_start,
                        streak_end=streak_end,
                        max_load=max_load,
                    )
                )

    return results


# ---------------------------------------------------------------------------
# 2. Blocker Summary
# ---------------------------------------------------------------------------


@router.get("/{team_id}/metrics/blockers", response_model=BlockerSummary)
async def blocker_summary(
    team_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    members = await _get_active_members(team_id, db)

    if not members:
        return BlockerSummary(by_type=[], recurring=[])

    # A log counts as "blocked" if it has a per-day blocker_type_id (override),
    # or if the parent Task.status is "blocked".  The day-level type takes
    # precedence for classification; fall back to Task.blocker_type_id.
    r = await db.execute(
        select(
            DailyWorkLog.blocker_type_id.label("log_blocker_type_id"),
            Task.blocker_type_id.label("task_blocker_type_id"),
            Task.title.label("task_title"),
            Project.name.label("proj_name"),
            DailyRecord.record_date,
            Task.id.label("task_id"),
        )
        .join(Task, DailyWorkLog.task_id == Task.id)
        .join(DailyRecord, DailyWorkLog.daily_record_id == DailyRecord.id)
        .join(Project, Task.project_id == Project.id)
        .where(
            DailyRecord.user_id.in_(members.keys()),
            DailyRecord.record_date >= start_date,
            DailyRecord.record_date <= end_date,
        )
        .where(
            (DailyWorkLog.blocker_type_id.isnot(None))
            | (Task.status == "blocked")
        )
    )
    rows = r.all()

    type_counts: dict[uuid.UUID | None, int] = defaultdict(int)
    recurring_map: dict[tuple[str, str], set[date]] = defaultdict(set)

    for row in rows:
        effective_type = row.log_blocker_type_id or row.task_blocker_type_id
        type_counts[effective_type] += 1
        recurring_map[(row.task_title, row.proj_name)].add(row.record_date)

    type_names: dict[uuid.UUID, str] = {}
    bt_ids = [tid for tid in type_counts if tid is not None]
    if bt_ids:
        bt_r = await db.execute(select(BlockerType).where(BlockerType.id.in_(bt_ids)))
        for bt in bt_r.scalars().all():
            type_names[bt.id] = bt.name

    by_type = [
        BlockerByType(
            type=type_names.get(tid, "Unknown") if tid else "Unspecified",
            count=cnt,
        )
        for tid, cnt in sorted(type_counts.items(), key=lambda x: -x[1])
    ]

    recurring = [
        RecurringBlocker(task_desc=desc, project=proj, days_blocked=len(dates))
        for (desc, proj), dates in recurring_map.items()
        if len(dates) > 1
    ]
    recurring.sort(key=lambda x: -x.days_blocked)

    return BlockerSummary(by_type=by_type, recurring=recurring)


# ---------------------------------------------------------------------------
# 3. Fragmentation
# ---------------------------------------------------------------------------


@router.get("/{team_id}/metrics/fragmentation", response_model=list[FragmentationEntry])
async def fragmentation(
    team_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    members = await _get_active_members(team_id, db)
    settings = await _get_settings(team_id, db)

    if not members:
        return []

    # Count distinct Tasks touched per (user, date) via DailyWorkLog
    r = await db.execute(
        select(
            DailyRecord.user_id,
            DailyRecord.record_date,
            DailyWorkLog.task_id,
        )
        .join(DailyWorkLog, DailyWorkLog.daily_record_id == DailyRecord.id)
        .where(
            DailyRecord.user_id.in_(members.keys()),
            DailyRecord.record_date >= start_date,
            DailyRecord.record_date <= end_date,
        )
    )
    rows = r.all()

    # Use a set per (user, date) to count distinct tasks
    task_sets: dict[tuple[uuid.UUID, date], set[uuid.UUID]] = defaultdict(set)
    for row in rows:
        task_sets[(row.user_id, row.record_date)].add(row.task_id)

    threshold = settings.fragmentation_task_threshold
    return [
        FragmentationEntry(
            user_id=uid,
            display_name=members[uid],
            date=d,
            task_count=len(task_ids),
        )
        for (uid, d), task_ids in sorted(task_sets.items(), key=lambda x: x[0])
        if len(task_ids) >= threshold
    ]


# ---------------------------------------------------------------------------
# 4. Carry-over Aging
# ---------------------------------------------------------------------------


@router.get(
    "/{team_id}/metrics/carryover-aging", response_model=list[CarryoverAgingEntry]
)
async def carryover_aging(
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    members = await _get_active_members(team_id, db)
    settings = await _get_settings(team_id, db)

    if not members:
        return []

    # Active (non-done) tasks owned by team members.
    # Aging = working days from Task.created_at.date() to today — no chain traversal.
    r = await db.execute(
        select(Task, Project.name.label("proj_name"))
        .join(Project, Task.project_id == Project.id)
        .where(
            Task.assignee_id.in_(members.keys()),
            Task.status.in_(["todo", "running", "blocked"]),
            Task.is_active.is_(True),
        )
    )
    rows = r.all()

    if not rows:
        return []

    today = datetime.now(UTC).date()
    threshold = settings.carryover_aging_days
    results: list[CarryoverAgingEntry] = []

    for task, proj_name in rows:
        root_date = task.created_at.date()
        days_aged = count_working_days(root_date, today)
        if days_aged >= threshold:
            results.append(
                CarryoverAgingEntry(
                    user_id=task.assignee_id,
                    display_name=members.get(task.assignee_id, "Unknown"),
                    task_desc=task.title,
                    project=proj_name,
                    root_date=root_date,
                    working_days_aged=days_aged,
                )
            )

    results.sort(key=lambda x: -x.working_days_aged)
    return results


# ---------------------------------------------------------------------------
# 5. Category Balance
# ---------------------------------------------------------------------------


@router.get("/{team_id}/metrics/balance", response_model=TeamBalance)
async def category_balance(
    team_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    members = await _get_active_members(team_id, db)
    settings = await _get_settings(team_id, db)

    if not members:
        return TeamBalance(
            members=[], team_aggregate={}, targets=settings.balance_targets
        )

    cat_r = await db.execute(select(Category.id, Category.name))
    cat_names: dict[uuid.UUID, str] = {row.id: row.name for row in cat_r.all()}

    # Effort is on DailyWorkLog; category is on Task
    r = await db.execute(
        select(DailyRecord.user_id, Task.category_id, DailyWorkLog.effort)
        .join(DailyWorkLog, DailyWorkLog.daily_record_id == DailyRecord.id)
        .join(Task, DailyWorkLog.task_id == Task.id)
        .where(
            DailyRecord.user_id.in_(members.keys()),
            DailyRecord.record_date >= start_date,
            DailyRecord.record_date <= end_date,
        )
    )
    rows = r.all()

    user_effort: dict[uuid.UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    team_effort: dict[str, int] = defaultdict(int)

    for row in rows:
        cat = cat_names.get(row.category_id, str(row.category_id)[:8])
        user_effort[row.user_id][cat] += row.effort
        team_effort[cat] += row.effort

    def _to_pct(effort_map: dict[str, int]) -> dict[str, float]:
        total = sum(effort_map.values())
        if total == 0:
            return {}
        return {k: round(v / total * 100, 1) for k, v in effort_map.items()}

    member_balances = [
        MemberBalance(
            user_id=uid,
            display_name=members[uid],
            categories=_to_pct(dict(user_effort[uid])),
        )
        for uid in members
    ]

    return TeamBalance(
        members=member_balances,
        team_aggregate=_to_pct(dict(team_effort)),
        targets=settings.balance_targets,
    )


# ---------------------------------------------------------------------------
# 6. Project Effort Overview
# ---------------------------------------------------------------------------


@router.get(
    "/{team_id}/metrics/project-effort", response_model=list[ProjectEffortEntry]
)
async def project_effort(
    team_id: uuid.UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_leader_or_admin(team_id, current_user, db)
    members = await _get_active_members(team_id, db)

    if not members:
        return []

    # Effort is on DailyWorkLog; project is on Task
    r = await db.execute(
        select(Project, DailyWorkLog.effort, DailyRecord.user_id)
        .join(Task, DailyWorkLog.task_id == Task.id)
        .join(Project, Task.project_id == Project.id)
        .join(DailyRecord, DailyWorkLog.daily_record_id == DailyRecord.id)
        .where(
            DailyRecord.user_id.in_(members.keys()),
            DailyRecord.record_date >= start_date,
            DailyRecord.record_date <= end_date,
        )
    )
    rows = r.all()

    proj_data: dict[uuid.UUID, dict] = {}
    for proj, effort, user_id in rows:
        if proj.id not in proj_data:
            proj_data[proj.id] = {
                "project": proj,
                "total": 0,
                "by_member": defaultdict(int),
            }
        proj_data[proj.id]["total"] += effort
        proj_data[proj.id]["by_member"][user_id] += effort

    results = []
    for pid, data in sorted(proj_data.items(), key=lambda x: -x[1]["total"]):
        p = data["project"]
        results.append(
            ProjectEffortEntry(
                project_id=pid,
                name=p.name,
                scope=p.scope.value,
                total_effort=data["total"],
                member_effort=[
                    MemberEffort(
                        user_id=uid,
                        display_name=members.get(uid, "Unknown"),
                        effort=eff,
                    )
                    for uid, eff in sorted(
                        data["by_member"].items(), key=lambda x: -x[1]
                    )
                ],
            )
        )
    return results
