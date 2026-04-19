"""
Quarterly Report endpoints:
  POST /quarterly-reports/generate             — start async generation
  GET  /quarterly-reports/{quarter}            — get own report (draft: owner; finalized: owner+leader+admin)
  PUT  /quarterly-reports/{quarter}            — edit draft (owner only)
  POST /quarterly-reports/{quarter}/finalize   — finalize (owner only)
  POST /quarterly-reports/{quarter}/regenerate — regenerate (owner only, resets to generating)
  GET  /teams/{team_id}/quarterly-reports      — leader: finalized reports for team members

Visibility invariant:
  draft = owner only
  finalized = owner + leader of owner's team + admin
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.engine import async_session_factory, get_db
from app.db.models.admin_settings import AdminSettings
from app.db.models.category import Category
from app.db.models.daily_record import DailyRecord
from app.db.models.project import Project
from app.db.models.quarterly_report import QuarterlyReport, QuarterlyReportStatus
from app.db.models.task import DailyWorkLog, Task
from app.db.models.team import TeamMembership
from app.db.models.user import User
from app.db.schemas.quarterly_report import (
    QuarterlyReportGenerate,
    QuarterlyReportRead,
    QuarterlyReportUpdate,
)
from app.services import llm
from app.services.notification import NotificationService

router = APIRouter(tags=["quarterly-reports"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_output_language(db: AsyncSession) -> str:
    r = await db.execute(
        select(AdminSettings).where(AdminSettings.key == "output_language")
    )
    setting = r.scalar_one_or_none()
    if setting is None:
        return "ja"
    val = setting.value
    return val if isinstance(val, str) else "ja"


def _quarter_date_range(quarter: str) -> tuple[datetime, datetime]:
    """Return (start, end_inclusive) as dates from a quarter string like '2026Q1'."""
    year = int(quarter[:4])
    q = int(quarter[5])
    month_start = (q - 1) * 3 + 1
    month_end = month_start + 2
    import calendar

    last_day = calendar.monthrange(year, month_end)[1]
    start = datetime(year, month_start, 1, tzinfo=UTC)
    end = datetime(year, month_end, last_day, 23, 59, 59, tzinfo=UTC)
    return start, end


async def _require_can_view(
    report: QuarterlyReport,
    current_user: User,
    db: AsyncSession,
) -> None:
    """Raise 403 unless the user can view this report."""
    if current_user.id == report.user_id:
        return
    if current_user.is_admin:
        return
    if report.status != QuarterlyReportStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    if current_user.is_leader:
        owner_mem = await db.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == report.user_id,
                TeamMembership.left_at.is_(None),
            )
        )
        leader_mem = await db.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.left_at.is_(None),
            )
        )
        if (
            owner_mem is not None
            and leader_mem is not None
            and owner_mem.team_id == leader_mem.team_id
        ):
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


async def _pre_aggregate(
    user_id: uuid.UUID,
    quarter: str,
    db: AsyncSession,
) -> tuple[dict, dict[str, list[str]], dict[str, list[str]]]:
    """
    Returns (pre_aggregated_data, day_notes_by_project, blocker_texts_by_project).
    pre_aggregated_data contains effort%, task counts, blocker counts, category breakdown.
    """
    start, end = _quarter_date_range(quarter)

    rec_result = await db.execute(
        select(DailyRecord).where(
            DailyRecord.user_id == user_id,
            DailyRecord.record_date >= start.date(),
            DailyRecord.record_date <= end.date(),
        )
    )
    records = rec_result.scalars().all()
    if not records:
        return {"days_reported": 0}, {}, {}

    record_ids = [r.id for r in records]

    # Fetch DailyWorkLogs + parent Tasks for the quarter's records
    log_result = await db.execute(
        select(DailyWorkLog, Task)
        .join(Task, DailyWorkLog.task_id == Task.id)
        .where(DailyWorkLog.daily_record_id.in_(record_ids))
    )
    log_task_pairs = log_result.all()

    # Name lookups
    proj_result = await db.execute(select(Project.id, Project.name))
    proj_names: dict[uuid.UUID, str] = {row.id: row.name for row in proj_result.all()}

    cat_result = await db.execute(select(Category.id, Category.name))
    cat_names: dict[uuid.UUID, str] = {row.id: row.name for row in cat_result.all()}

    # Aggregation
    proj_effort: dict[str, int] = defaultdict(int)
    proj_task_count: dict[str, int] = defaultdict(int)
    proj_blocker_count: dict[str, int] = defaultdict(int)
    cat_effort: dict[str, int] = defaultdict(int)
    total_effort = 0
    seen_tasks: set[uuid.UUID] = set()

    day_notes_by_proj: dict[str, list[str]] = defaultdict(list)
    blocker_texts_by_proj: dict[str, list[str]] = defaultdict(list)

    for log, task in log_task_pairs:
        proj = proj_names.get(task.project_id, "?")
        cat = cat_names.get(task.category_id, "?")
        proj_effort[proj] += log.effort
        total_effort += log.effort
        cat_effort[cat] += log.effort
        if task.id not in seen_tasks:
            proj_task_count[proj] += 1
            if task.status == "blocked":
                proj_blocker_count[proj] += 1
        seen_tasks.add(task.id)
        if log.blocker_text:
            blocker_texts_by_proj[proj].append(log.blocker_text)

    # Collect day notes per project (one note per record, deduped)
    record_day_notes: dict[uuid.UUID, str | None] = {r.id: r.day_note for r in records}
    record_proj: dict[uuid.UUID, set[str]] = defaultdict(set)
    for log, task in log_task_pairs:
        if log.daily_record_id in record_day_notes:
            record_proj[log.daily_record_id].add(proj_names.get(task.project_id, "?"))

    for rec_id, note in record_day_notes.items():
        if note:
            for proj in record_proj.get(rec_id, []):
                if note not in day_notes_by_proj[proj]:
                    day_notes_by_proj[proj].append(note)

    # Effort %
    proj_effort_pct = {
        proj: round(effort / total_effort * 100, 1) if total_effort else 0
        for proj, effort in proj_effort.items()
    }

    pre_aggregated = {
        "days_reported": len(records),
        "total_tasks": len(seen_tasks),
        "total_effort": total_effort,
        "project_effort_pct": proj_effort_pct,
        "project_task_counts": dict(proj_task_count),
        "project_blocker_counts": dict(proj_blocker_count),
        "category_effort": dict(cat_effort),
    }

    return pre_aggregated, dict(day_notes_by_proj), dict(blocker_texts_by_proj)


async def _run_generation(report_id: uuid.UUID) -> None:
    """Background task: aggregate data, call LLM, update report to draft."""
    async with async_session_factory() as db:
        report = await db.scalar(
            select(QuarterlyReport).where(QuarterlyReport.id == report_id)
        )
        if report is None:
            return

        user = await db.scalar(select(User).where(User.id == report.user_id))
        if user is None:
            return

        output_language = await _get_output_language(db)

        try:
            pre_data, day_notes, blocker_texts = await _pre_aggregate(
                report.user_id, report.quarter, db
            )
            sections = await llm.generate_quarterly_report(
                display_name=user.display_name,
                quarter=report.quarter,
                output_language=output_language,
                pre_aggregated_data=pre_data,
                day_notes_by_project=day_notes,
                blocker_texts_by_project=blocker_texts,
                guidance_text=report.guidance_text,
            )
            report.data = pre_data
            report.sections = sections
            report.status = QuarterlyReportStatus.draft
        except Exception:
            # If generation fails, leave as generating — caller can retry
            return

        await db.commit()

        # Notify member
        svc = NotificationService(db)
        await svc.send(
            user_id=report.user_id,
            trigger_type="quarterly_draft_ready",
            title="Quarterly report draft is ready",
            body=f"Your {report.quarter} quarterly report draft is ready for review.",
            data={"quarter": report.quarter, "report_id": str(report.id)},
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/quarterly-reports/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=QuarterlyReportRead,
)
async def generate_quarterly_report(
    body: QuarterlyReportGenerate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # One report per (user, quarter); reject duplicate generating/draft report
    existing = await db.scalar(
        select(QuarterlyReport).where(
            QuarterlyReport.user_id == current_user.id,
            QuarterlyReport.quarter == body.quarter,
        )
    )
    if existing is not None and existing.status != QuarterlyReportStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A report for this quarter already exists. Use regenerate to restart.",
        )

    guidance = body.guidance_text[:2000] if body.guidance_text else None

    if existing is not None:
        # Finalized — allow creating a new draft by resetting
        existing.status = QuarterlyReportStatus.generating
        existing.guidance_text = guidance
        existing.sections = None
        existing.data = None
        existing.finalized_at = None
        report = existing
    else:
        report = QuarterlyReport(
            user_id=current_user.id,
            quarter=body.quarter,
            status=QuarterlyReportStatus.generating,
            guidance_text=guidance,
        )
        db.add(report)

    await db.commit()
    await db.refresh(report)

    asyncio.create_task(_run_generation(report.id))

    return QuarterlyReportRead.model_validate(report)


@router.get(
    "/quarterly-reports/{quarter}",
    response_model=QuarterlyReportRead,
)
async def get_quarterly_report(
    quarter: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.scalar(
        select(QuarterlyReport).where(
            QuarterlyReport.user_id == current_user.id,
            QuarterlyReport.quarter == quarter,
        )
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    await _require_can_view(report, current_user, db)
    return QuarterlyReportRead.model_validate(report)


@router.put(
    "/quarterly-reports/{quarter}",
    response_model=QuarterlyReportRead,
)
async def update_quarterly_report(
    quarter: str,
    body: QuarterlyReportUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.scalar(
        select(QuarterlyReport).where(
            QuarterlyReport.user_id == current_user.id,
            QuarterlyReport.quarter == quarter,
        )
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    if report.status != QuarterlyReportStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only draft reports can be edited.",
        )

    if body.sections is not None:
        report.sections = body.sections
    if body.guidance_text is not None:
        report.guidance_text = body.guidance_text[:2000]

    await db.commit()
    await db.refresh(report)
    return QuarterlyReportRead.model_validate(report)


@router.post(
    "/quarterly-reports/{quarter}/finalize",
    response_model=QuarterlyReportRead,
)
async def finalize_quarterly_report(
    quarter: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.scalar(
        select(QuarterlyReport).where(
            QuarterlyReport.user_id == current_user.id,
            QuarterlyReport.quarter == quarter,
        )
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    if report.status != QuarterlyReportStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only draft reports can be finalized.",
        )

    report.status = QuarterlyReportStatus.finalized
    report.finalized_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(report)
    return QuarterlyReportRead.model_validate(report)


@router.post(
    "/quarterly-reports/{quarter}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=QuarterlyReportRead,
)
async def regenerate_quarterly_report(
    quarter: str,
    body: QuarterlyReportUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.scalar(
        select(QuarterlyReport).where(
            QuarterlyReport.user_id == current_user.id,
            QuarterlyReport.quarter == quarter,
        )
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    if report.status == QuarterlyReportStatus.finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Finalized reports cannot be regenerated.",
        )

    report.status = QuarterlyReportStatus.generating
    report.sections = None
    report.data = None
    if body.guidance_text is not None:
        report.guidance_text = body.guidance_text[:2000]

    await db.commit()
    await db.refresh(report)

    asyncio.create_task(_run_generation(report.id))
    return QuarterlyReportRead.model_validate(report)


@router.get(
    "/teams/{team_id}/quarterly-reports",
    response_model=list[QuarterlyReportRead],
)
async def list_team_quarterly_reports(
    team_id: uuid.UUID,
    quarter: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.is_admin and not current_user.is_leader:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    if not current_user.is_admin:
        leader_mem = await db.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.team_id == team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        if leader_mem is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a leader of this team",
            )

    member_ids_result = await db.execute(
        select(TeamMembership.user_id).where(
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    member_ids = [row[0] for row in member_ids_result.all()]

    stmt = select(QuarterlyReport).where(
        QuarterlyReport.user_id.in_(member_ids),
        QuarterlyReport.status == QuarterlyReportStatus.finalized,
    )
    if quarter is not None:
        stmt = stmt.where(QuarterlyReport.quarter == quarter)

    result = await db.execute(stmt)
    return [QuarterlyReportRead.model_validate(r) for r in result.scalars().all()]
