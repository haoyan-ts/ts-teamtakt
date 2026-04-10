"""GET /users/me/growth — personal growth trends (self-scoped only)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user
from app.db.engine import get_db
from app.db.models.category import Category
from app.db.models.daily_record import DailyRecord
from app.db.models.task_entry import TaskEntry
from app.db.models.user import User
from app.db.schemas.metrics import (
    GrowthResponse,
    MonthlyBalance,
    MonthlyBlockerCount,
    WeeklyLoad,
)

router = APIRouter(tags=["growth"])


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def _week_start(d: date) -> date:
    """Return Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


@router.get("/users/me/growth", response_model=GrowthResponse)
async def get_personal_growth(
    months: int = Query(3, ge=1, le=12),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    cutoff = date.today() - timedelta(days=months * 30)

    # --- Fetch records and task entries ---
    rec_r = await db.execute(
        select(DailyRecord)
        .where(
            DailyRecord.user_id == current_user.id,
            DailyRecord.record_date >= cutoff,
        )
        .order_by(DailyRecord.record_date)
    )
    records = rec_r.scalars().all()

    if not records:
        return GrowthResponse(balance_trend=[], load_trend=[], blocker_trend=[])

    record_ids = [r.id for r in records]
    te_r = await db.execute(
        select(TaskEntry).where(TaskEntry.daily_record_id.in_(record_ids))
    )
    task_entries = te_r.scalars().all()

    # Category names
    cat_r = await db.execute(select(Category.id, Category.name))
    cat_names = {row.id: row.name for row in cat_r.all()}

    # --- Balance trend: monthly category % ---
    record_by_id = {r.id: r for r in records}
    monthly_effort: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    monthly_blockers: dict[str, int] = defaultdict(int)

    for te in task_entries:
        rec = record_by_id[te.daily_record_id]
        m = _month_key(rec.record_date)
        cat = cat_names.get(te.category_id, "Other")
        monthly_effort[m][cat] += te.effort
        if te.status == "blocked":
            monthly_blockers[m] += 1

    balance_trend: list[MonthlyBalance] = []
    for m in sorted(monthly_effort.keys()):
        total = sum(monthly_effort[m].values())
        pct = (
            {k: round(v / total * 100, 1) for k, v in monthly_effort[m].items()}
            if total
            else {}
        )
        balance_trend.append(MonthlyBalance(month=m, categories=pct))

    # --- Load trend: weekly average ---
    weekly_loads: dict[date, list[int]] = defaultdict(list)
    for rec in records:
        ws = _week_start(rec.record_date)
        weekly_loads[ws].append(rec.day_load)

    load_trend = [
        WeeklyLoad(week_start=ws, avg_load=round(sum(loads) / len(loads), 2))
        for ws, loads in sorted(weekly_loads.items())
    ]

    # --- Blocker trend: monthly count ---
    blocker_trend = [
        MonthlyBlockerCount(month=m, count=cnt)
        for m, cnt in sorted(monthly_blockers.items())
    ]

    return GrowthResponse(
        balance_trend=balance_trend,
        load_trend=load_trend,
        blocker_trend=blocker_trend,
    )
