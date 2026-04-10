"""
Calendar working-day utilities.

count_working_days() — pure function, weekend-only (no DB needed).
count_working_days_db() — async, also excludes holidays from holiday_calendar.

Phase G wired is_working_day_db() to use the holiday_calendar table.
"""

from __future__ import annotations

from datetime import date, timedelta


def count_working_days(start: date, end_inclusive: date) -> int:
    """Count Mon–Fri days in [start, end_inclusive].  Returns 0 if start > end_inclusive."""
    if start > end_inclusive:
        return 0
    count = 0
    current = start
    while current <= end_inclusive:
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            count += 1
        current += timedelta(days=1)
    return count


def is_working_day(d: date) -> bool:
    """Return True when d is Mon–Fri (weekend-only check, no holiday DB query)."""
    return d.weekday() < 5


# ---------------------------------------------------------------------------
# DB-aware versions (Phase G)
# ---------------------------------------------------------------------------


async def is_working_day_db(d: date, db) -> bool:
    """
    Return True when d is a working day, accounting for holiday_calendar.
    - Mon-Fri days become False if they appear in holiday_calendar (is_workday=False, default).
    - Weekend days become True if holiday_calendar marks them is_workday=True (exchanged workdays).
    """
    from sqlalchemy import select

    from app.db.models.notification_preference import HolidayCalendar

    r = await db.execute(select(HolidayCalendar).where(HolidayCalendar.date == d))
    holiday = r.scalar_one_or_none()

    if holiday:
        # If the record exists with is_workday=True, it's an exchanged workday (treat as working)
        return holiday.is_workday
    # Default: Mon-Fri is working
    return d.weekday() < 5


async def count_working_days_db(start: date, end_inclusive: date, db) -> int:
    """Count working days accounting for holiday_calendar."""
    if start > end_inclusive:
        return 0
    count = 0
    current = start
    while current <= end_inclusive:
        if await is_working_day_db(current, db):
            count += 1
        current += timedelta(days=1)
    return count
