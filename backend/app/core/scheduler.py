"""
APScheduler jobs for time-based notification triggers.

Jobs:
  - check_missing_days: daily at 10:00 JST
      For each active user, if the previous working day has no DailyRecord,
      send a missing_day notification.
  - check_edit_window_closing: Friday at 17:00 JST
      For each user whose current-week records are incomplete and whose
      edit window is still open, send an edit_window_closing notification.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.working_days import is_working_day_db
from app.db.engine import async_session_factory
from app.db.models.daily_record import DailyRecord
from app.db.models.team import TeamMembership
from app.db.models.user import User
from app.services.notification import NotificationService

JST = pytz.timezone("Asia/Tokyo")

scheduler = AsyncIOScheduler(timezone=JST)


def _previous_working_day(today: date) -> date | None:
    """Return the most-recent calendar day before today that is Mon–Fri.
    Returns None only if today is before the epoch (should never happen)."""
    candidate = today - timedelta(days=1)
    # Walk back up to 7 days to skip weekends/holidays
    for _ in range(7):
        if candidate.weekday() < 5:  # rough weekend check; DB check happens later
            return candidate
        candidate -= timedelta(days=1)
    return None


async def check_missing_days() -> None:
    """Daily job (10:00 JST): notify users who have no record for the previous working day."""
    today = date.today()
    async with async_session_factory() as db:
        prev = _previous_working_day(today)
        if prev is None:
            return

        # Honour the DB holiday calendar
        if not await is_working_day_db(prev, db):
            return

        # All active users (have at least one active team membership)
        result = await db.execute(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(TeamMembership.left_at.is_(None))
            .distinct()
        )
        users = result.scalars().all()

        svc = NotificationService(db)
        for user in users:
            has_record = await db.scalar(
                select(DailyRecord).where(
                    DailyRecord.user_id == user.id,
                    DailyRecord.record_date == prev,
                )
            )
            if has_record is None:
                await svc.send(
                    user_id=user.id,
                    trigger_type="missing_day",
                    title="Daily record missing",
                    body=f"You have not submitted a record for {prev.isoformat()}.",
                    data={"record_date": prev.isoformat()},
                )

        await db.commit()


async def check_edit_window_closing() -> None:
    """Friday 17:00 JST: notify users with incomplete records for the current week."""
    from app.core.edit_window import compute_edit_deadline

    today = date.today()
    # Monday of current week
    week_start = today - timedelta(days=today.weekday())

    async with async_session_factory() as db:
        result = await db.execute(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(TeamMembership.left_at.is_(None))
            .distinct()
        )
        users = result.scalars().all()

        svc = NotificationService(db)
        for user in users:
            # Count working days in current week that have a record
            submitted = 0
            missing_dates: list[date] = []
            for offset in range(5):  # Mon–Fri
                day = week_start + timedelta(days=offset)
                if day > today:
                    break
                if not await is_working_day_db(day, db):
                    continue
                has_record = await db.scalar(
                    select(DailyRecord).where(
                        DailyRecord.user_id == user.id,
                        DailyRecord.record_date == day,
                    )
                )
                if has_record is not None:
                    submitted += 1
                else:
                    missing_dates.append(day)

            if missing_dates:
                deadline = compute_edit_deadline(week_start)
                await svc.send(
                    user_id=user.id,
                    trigger_type="edit_window_closing",
                    title="Edit window closing soon",
                    body=(
                        f"You have {len(missing_dates)} unsubmitted day(s) this week. "
                        f"Deadline: {deadline.strftime('%Y-%m-%d %H:%M')} JST."
                    ),
                    data={
                        "missing_dates": [d.isoformat() for d in missing_dates],
                        "deadline": deadline.isoformat(),
                    },
                )

        await db.commit()


def start_scheduler() -> None:
    scheduler.add_job(
        check_missing_days,
        trigger="cron",
        hour=10,
        minute=0,
        id="check_missing_days",
        replace_existing=True,
    )
    scheduler.add_job(
        check_edit_window_closing,
        trigger="cron",
        day_of_week="fri",
        hour=17,
        minute=0,
        id="check_edit_window_closing",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
