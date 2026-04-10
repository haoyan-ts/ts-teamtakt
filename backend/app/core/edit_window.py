from datetime import date, datetime, timedelta

import pytz

JST = pytz.timezone("Asia/Tokyo")


def _now_jst() -> datetime:
    """Return the current time in JST. Extracted for testability."""
    return datetime.now(JST)


def monday_of_week(d: date) -> date:
    """Return the Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def compute_edit_deadline(record_date: date) -> datetime:
    """edit_deadline = record_week_start (Monday) + 12 days = Saturday 00:00 JST"""
    week_start = monday_of_week(record_date)
    saturday = week_start + timedelta(days=12)
    return JST.localize(datetime(saturday.year, saturday.month, saturday.day, 0, 0, 0))


def check_edit_window(record_date: date, form_opened_at: datetime) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).

    Rules:
    1. If now_jst < edit_deadline → allowed
    2. If form_opened_at < edit_deadline AND now_jst < edit_deadline + 15min → allowed (grace)
    3. form_opened_at must be within last 6 hours — if older, reject even in grace period
    4. Otherwise → rejected
    """
    now_jst = _now_jst()
    deadline = compute_edit_deadline(record_date)

    if form_opened_at.tzinfo is None:
        form_opened_at = pytz.utc.localize(form_opened_at)
    form_opened_jst = form_opened_at.astimezone(JST)

    if (now_jst - form_opened_jst).total_seconds() > 6 * 3600:
        return (
            False,
            "form_opened_at is stale (older than 6 hours). Please reopen the form.",
        )

    if now_jst < deadline:
        return True, ""

    if form_opened_jst < deadline and now_jst < deadline + timedelta(minutes=15):
        return True, ""  # grace period

    return False, "Edit window closed. Contact your leader for an unlock."


def has_active_unlock(unlock_grants, user_id, record_date: date) -> bool:
    """Check if there's an active unlock grant for (user_id, record_date)."""
    for grant in unlock_grants:
        if (
            grant.user_id == user_id
            and grant.record_date == record_date
            and grant.revoked_at is None
        ):
            return True
    return False
