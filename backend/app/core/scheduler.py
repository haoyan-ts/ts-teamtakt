"""
APScheduler jobs for time-based notification triggers.

Jobs:
  - check_missing_days: daily at 10:00 JST
      For each active user, if the previous working day has no DailyRecord,
      send a missing_day notification.
  - check_edit_window_closing: Friday at 17:00 JST
      For each user whose current-week records are incomplete and whose
      edit window is still open, send an edit_window_closing notification.
  - publish_teams_weekly_reports: Saturday 00:00 JST
      For each team with a configured MS Teams channel, post each active
      member's finalized weekly report to the channel.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import httpx
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.core.working_days import is_working_day_db
from app.db.engine import async_session_factory
from app.db.models.admin_settings import AdminSettings
from app.db.models.daily_record import DailyRecord
from app.db.models.team import Team, TeamMembership
from app.db.models.user import User
from app.db.models.weekly_report import TeamsPostRecord, TeamsPostStatus, WeeklyReport
from app.services import graph_teams
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)

_MS_TEAMS_CONFIG_KEY = "ms_teams_config"
_TEAMS_COOLDOWN_MINUTES = 5


def _teams_idempotency_key(user_id: object, week_start: date) -> str:
    return f"teams:{user_id}:{week_start}"


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


async def publish_teams_weekly_reports() -> None:
    """Saturday 00:00 JST: post each member's finalized weekly report to MS Teams."""
    today = date.today()
    # Saturday's week_start is the Monday 5 days prior
    week_start = today - timedelta(days=5)

    async with async_session_factory() as db:
        teams_result = await db.execute(select(Team))
        teams = teams_result.scalars().all()

        for team in teams:
            # Resolve MS Teams channel config for this team
            cfg_r = await db.execute(
                select(AdminSettings).where(
                    AdminSettings.key == _MS_TEAMS_CONFIG_KEY,
                    AdminSettings.team_id == team.id,
                )
            )
            cfg = cfg_r.scalar_one_or_none()

            if cfg is None or not cfg.teams_team_id or not cfg.teams_channel_id:
                logger.debug(
                    "publish_teams_weekly_reports: team %s has no Teams channel config; skipping",
                    team.id,
                )
                continue

            # Get active members for this team
            mem_r = await db.execute(
                select(TeamMembership).where(
                    TeamMembership.team_id == team.id,
                    TeamMembership.left_at.is_(None),
                )
            )
            memberships = mem_r.scalars().all()

            for membership in memberships:
                user_id = membership.user_id

                # Look up finalized weekly report
                report_r = await db.execute(
                    select(WeeklyReport).where(
                        WeeklyReport.user_id == user_id,
                        WeeklyReport.week_start == week_start,
                    )
                )
                report = report_r.scalar_one_or_none()
                if report is None:
                    logger.debug(
                        "publish_teams_weekly_reports: no report for user %s week %s; skipping",
                        user_id,
                        week_start,
                    )
                    continue

                # Idempotency / cooldown check
                idem_key = _teams_idempotency_key(user_id, week_start)
                tpr_r = await db.execute(
                    select(TeamsPostRecord).where(
                        TeamsPostRecord.idempotency_key == idem_key
                    )
                )
                tpr = tpr_r.scalar_one_or_none()

                if tpr and tpr.posted_at:
                    posted_at = (
                        tpr.posted_at
                        if tpr.posted_at.tzinfo
                        else tpr.posted_at.replace(tzinfo=UTC)
                    )
                    if datetime.now(UTC) - posted_at < timedelta(
                        minutes=_TEAMS_COOLDOWN_MINUTES
                    ):
                        logger.debug(
                            "publish_teams_weekly_reports: user %s within cooldown; skipping",
                            user_id,
                        )
                        continue

                # Fetch user for token and display name
                user_r = await db.execute(select(User).where(User.id == user_id))
                user = user_r.scalar_one_or_none()
                if user is None or not user.ms_graph_refresh_token:
                    logger.warning(
                        "publish_teams_weekly_reports: user %s has no ms_graph_refresh_token; skipping",
                        user_id,
                    )
                    continue

                # Upsert TeamsPostRecord
                if tpr is None:
                    tpr = TeamsPostRecord(
                        user_id=user_id,
                        week_start=week_start,
                        idempotency_key=idem_key,
                        status=TeamsPostStatus.pending,
                    )
                    db.add(tpr)
                    await db.flush()

                # Build message from public data only (category_breakdown has no private fields)
                effort_summary: dict[str, int] = (report.data or {}).get(
                    "category_breakdown", {}
                )
                week_end = week_start + timedelta(days=6)
                report_url = f"{settings.FRONTEND_URL}/weekly-reports/{report.id}"
                html_body = graph_teams.build_teams_message(
                    member_name=user.display_name,
                    week_start=str(week_start),
                    week_end=str(week_end),
                    effort_summary=effort_summary,
                    report_url=report_url,
                )

                tpr.posted_at = datetime.now(UTC)
                try:
                    access_token, new_refresh = await graph_teams.refresh_graph_token(
                        user.ms_graph_refresh_token
                    )
                    user.ms_graph_refresh_token = new_refresh
                    db.add(user)

                    await graph_teams.post_channel_message(
                        access_token=access_token,
                        teams_team_id=cfg.teams_team_id,
                        teams_channel_id=cfg.teams_channel_id,
                        html_body=html_body,
                    )
                    tpr.status = TeamsPostStatus.posted
                    tpr.error_message = None
                except Exception as exc:
                    tpr.status = TeamsPostStatus.failed
                    tpr.error_message = str(exc)[:500]
                    logger.warning(
                        "publish_teams_weekly_reports: Teams post failed for user %s: %s",
                        user_id,
                        exc,
                    )

                    notif_svc = NotificationService(db)
                    await notif_svc.send(
                        user_id=user_id,
                        trigger_type="weekly_report_ready",
                        title="Teams投稿に失敗しました",
                        body=f"Week of {week_start}: {tpr.error_message}",
                        data={
                            "week_start": str(week_start),
                            "error": tpr.error_message,
                        },
                    )

                await db.commit()


async def validate_github_tokens() -> None:
    """Daily 03:00 JST: validate all stored GitHub tokens; clear and notify on 401."""
    from app.core.token_encryption import decrypt_token

    enc_key = settings.GITHUB_TOKEN_ENCRYPTION_KEY
    _GITHUB_USER_URL = "https://api.github.com/user"

    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.github_access_token_enc.is_not(None))
        )
        users = result.scalars().all()

        svc = NotificationService(db)
        for user in users:
            assert user.github_access_token_enc is not None
            try:
                if enc_key and user.github_token_iv:
                    raw_token = decrypt_token(
                        user.github_access_token_enc, user.github_token_iv, enc_key
                    )
                else:
                    raw_token = user.github_access_token_enc
            except Exception:
                logger.warning(
                    "validate_github_tokens: failed to decrypt token for user %s; clearing",
                    user.id,
                )
                user.github_access_token_enc = None
                user.github_token_iv = None
                user.github_login = None
                await db.commit()
                continue

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        _GITHUB_USER_URL,
                        headers={
                            "Authorization": f"Bearer {raw_token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                    )
            except Exception as exc:
                logger.warning(
                    "validate_github_tokens: network error for user %s: %s",
                    user.id,
                    exc,
                )
                continue

            if resp.status_code == 401:
                logger.info(
                    "validate_github_tokens: revoked token for user %s; clearing",
                    user.id,
                )
                user.github_access_token_enc = None
                user.github_token_iv = None
                user.github_login = None
                await svc.send(
                    user_id=user.id,
                    trigger_type="github_token_revoked",
                    title="GitHub account disconnected",
                    body=(
                        "Your GitHub token was revoked. "
                        "Please re-link your GitHub account in Profile Settings."
                    ),
                    data={"action": "relink_github"},
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
    scheduler.add_job(
        publish_teams_weekly_reports,
        trigger="cron",
        day_of_week="sat",
        hour=0,
        minute=0,
        id="publish_teams_weekly_reports",
        replace_existing=True,
    )
    scheduler.add_job(
        validate_github_tokens,
        trigger="cron",
        hour=3,
        minute=0,
        id="validate_github_tokens",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
