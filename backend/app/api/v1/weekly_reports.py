"""
Weekly Report generation and retrieval endpoints.

POST /weekly-reports/generate?week_start=YYYY-MM-DD
GET  /weekly-reports?week_start=YYYY-MM-DD  (user_id defaults to me)

Team Summary:
POST /weekly-reports/team-summary?team_id=&week_start=
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user
from app.db.engine import get_db
from app.db.models.category import Category, CategorySubType
from app.db.models.daily_record import DailyRecord
from app.db.models.project import Project
from app.db.models.task import DailyWorkLog, DailyWorkLogSelfAssessmentTag, Task
from app.db.models.user import User
from app.db.models.weekly_report import WeeklyReport
from app.db.schemas.weekly_report import WeeklyReportData, WeeklyReportSummaryResponse
from app.services.notification import NotificationService

router = APIRouter(prefix="/weekly-reports", tags=["weekly-reports"])


def _week_dates(week_start: date) -> list[date]:
    """Return Mon–Sun of the week starting at week_start."""
    return [week_start + timedelta(days=i) for i in range(7)]


def _is_after_window_close(week_start: date) -> bool:
    """Check that the edit window for this week has already closed (Sat 00:00 JST)."""
    # window_close = week_start + 12 days (Saturday 00:00 JST)
    window_close = week_start + timedelta(days=12)
    return date.today() >= window_close


@router.post(
    "/generate",
    response_model=WeeklyReportSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_weekly_report(
    week_start: date = Query(...),
    target_user_id: uuid.UUID | None = Query(
        None, description="Admin only: generate for another user"
    ),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Permission check
    if target_user_id and target_user_id != current_user.id:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
            )
        user_id = target_user_id
    else:
        user_id = current_user.id

    if not _is_after_window_close(week_start):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Weekly report can only be generated after the edit window closes (Saturday).",
        )

    # Fetch daily records for this week
    dates = _week_dates(week_start)
    rec_r = await db.execute(
        select(DailyRecord).where(
            DailyRecord.user_id == user_id,
            DailyRecord.record_date.in_(dates),
        )
    )
    records = rec_r.scalars().all()
    record_ids = [r.id for r in records]

    # Fetch DailyWorkLogs and their parent Tasks for this week's records
    logs_r = await db.execute(
        select(DailyWorkLog, Task)
        .join(Task, DailyWorkLog.task_id == Task.id)
        .where(DailyWorkLog.daily_record_id.in_(record_ids))
        if record_ids
        else select(DailyWorkLog, Task).where(false())
    )
    log_task_pairs = logs_r.all()
    work_logs = [log for log, _ in log_task_pairs]

    # Categories, sub-types, projects
    cat_r = await db.execute(select(Category.id, Category.name))
    cat_names: dict[uuid.UUID, str] = {row.id: row.name for row in cat_r.all()}

    sub_r = await db.execute(select(CategorySubType.id, CategorySubType.name))
    sub_names: dict[uuid.UUID, str] = {row.id: row.name for row in sub_r.all()}

    proj_r = await db.execute(select(Project.id, Project.name))
    proj_names: dict[uuid.UUID, str] = {row.id: row.name for row in proj_r.all()}

    # Self-assessment tags on work logs
    log_ids = [log.id for log in work_logs]
    tag_r = await db.execute(
        select(
            DailyWorkLogSelfAssessmentTag.self_assessment_tag_id,
            DailyWorkLogSelfAssessmentTag.daily_work_log_id,
        ).where(DailyWorkLogSelfAssessmentTag.daily_work_log_id.in_(log_ids))
        if log_ids
        else select(DailyWorkLogSelfAssessmentTag).where(false())
    )
    tag_rows = tag_r.all()

    # Aggregate
    cat_effort: dict[str, int] = defaultdict(int)
    sub_effort: dict[str, int] = defaultdict(int)
    proj_effort: dict[str, int] = defaultdict(int)
    carry_overs = []
    blockers = []
    total_load = sum(r.day_load for r in records)
    tag_counts: dict[str, int] = defaultdict(int)
    seen_tasks: set[uuid.UUID] = set()

    tag_by_log: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for row in tag_rows:
        tag_by_log[row.daily_work_log_id].append(row.self_assessment_tag_id)

    for log, task in log_task_pairs:
        cat_effort[cat_names.get(task.category_id, "?")] += log.effort
        if task.sub_type_id:
            sub_effort[sub_names.get(task.sub_type_id, "?")] += log.effort
        proj_effort[proj_names.get(task.project_id, "?")] += log.effort
        if task.status in ("running", "blocked") and task.id not in seen_tasks:
            carry_overs.append(
                {
                    "task_desc": task.title,
                    "project": proj_names.get(task.project_id, "?"),
                    "status": task.status,
                }
            )
        if task.status == "blocked" and task.id not in seen_tasks:
            blockers.append(
                {
                    "task_desc": task.title,
                    "project": proj_names.get(task.project_id, "?"),
                }
            )
        seen_tasks.add(task.id)
        for tag_id in tag_by_log[log.id]:
            tag_counts[str(tag_id)] += 1

    top_projects = [
        {"name": k, "effort": v}
        for k, v in sorted(proj_effort.items(), key=lambda x: -x[1])[:5]
    ]

    data = WeeklyReportData(
        days_reported=len(records),
        total_tasks=len(seen_tasks),
        avg_day_load=round(total_load / len(records), 2) if records else 0.0,
        category_breakdown=dict(cat_effort),
        sub_type_breakdown=dict(sub_effort),
        top_projects=top_projects,
        carry_overs=carry_overs,
        blockers=blockers,
        tag_distribution=dict(tag_counts),
    ).model_dump()

    # Upsert WeeklyReport
    existing_r = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.user_id == user_id,
            WeeklyReport.week_start == week_start,
        )
    )
    report = existing_r.scalar_one_or_none()
    if report:
        report.data = data
    else:
        report = WeeklyReport(user_id=user_id, week_start=week_start, data=data)
        db.add(report)

    await db.commit()
    await db.refresh(report)

    # Notify user that weekly report is ready
    notif_svc = NotificationService(db)
    await notif_svc.send(
        user_id=user_id,
        trigger_type="weekly_report_ready",
        title="週報が準備できました",
        body=f"Week of {week_start} report is ready.",
        data={"week_start": str(week_start)},
    )
    await db.commit()

    return WeeklyReportSummaryResponse(
        id=report.id,
        user_id=report.user_id,
        week_start=report.week_start,
        data=report.data,
        created_at=report.created_at.isoformat(),
    )


@router.get("", response_model=list[WeeklyReportSummaryResponse])
async def get_weekly_reports(
    week_start: date | None = Query(None),
    target_user_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user.id
    if target_user_id and target_user_id != current_user.id:
        if not current_user.is_admin and not current_user.is_leader:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        user_id = target_user_id

    q = select(WeeklyReport).where(WeeklyReport.user_id == user_id)
    if week_start:
        q = q.where(WeeklyReport.week_start == week_start)
    q = q.order_by(WeeklyReport.week_start.desc())

    r = await db.execute(q)
    reports = r.scalars().all()
    return [
        WeeklyReportSummaryResponse(
            id=rep.id,
            user_id=rep.user_id,
            week_start=rep.week_start,
            data=rep.data,
            created_at=rep.created_at.isoformat(),
        )
        for rep in reports
    ]
