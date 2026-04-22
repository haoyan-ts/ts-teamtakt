"""Tests for MS Teams channel publish service (issue #54).

Key invariants tested:
1. Happy path: message posted to configured channel → 200, status "posted"
2. Idempotency: second call within 5-minute cooldown → 429, no duplicate Graph call
3. Visibility: private fields (day_load, blocker_text) excluded from message payload
4. Skip (NULL channel config): Teams channel fields NULL → 422, no Graph call
5. Skip (no AdminSettings row): no config row at all → 422, no Graph call
6. Scheduler integration: publish_teams_weekly_reports() posts for each active member
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.core.scheduler import publish_teams_weekly_reports
from app.core.security import create_access_token
from app.db.models.admin_settings import AdminSettings
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User
from app.db.models.weekly_report import TeamsPostRecord, TeamsPostStatus, WeeklyReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A Monday safely in the past so edit window is closed
PAST_WEEK = date(2026, 1, 5)  # Monday; window closed Sat 2026-01-17


async def make_user(
    db, email: str, *, refresh_token: str | None = "fake-refresh-token"
):
    user = User(
        email=email,
        display_name=email.split("@")[0],
        ms_graph_refresh_token=refresh_token,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return user, token


async def make_team(db, name: str):
    team = Team(name=name)
    db.add(team)
    await db.flush()
    db.add(TeamSettings(team_id=team.id))
    await db.commit()
    await db.refresh(team)
    return team


async def make_membership(db, user_id, team_id):
    m = TeamMembership(user_id=user_id, team_id=team_id, joined_at=datetime.now(UTC))
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def make_weekly_report(db, user_id, week_start, *, data: dict | None = None):
    rpt = WeeklyReport(
        user_id=user_id,
        week_start=week_start,
        data=data if data is not None else {"category_breakdown": {"Dev": 5}},
    )
    db.add(rpt)
    await db.commit()
    await db.refresh(rpt)
    return rpt


async def make_admin_settings(
    db,
    team_id,
    *,
    teams_team_id: str | None = "team-111",
    teams_channel_id: str | None = "channel-222",
):
    cfg = AdminSettings(
        key="ms_teams_config",
        value={},
        team_id=team_id,
        teams_team_id=teams_team_id,
        teams_channel_id=teams_channel_id,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Happy path: message posted to configured channel
# ---------------------------------------------------------------------------


async def test_teams_post_happy_path(client, db_session):
    user, tok = await make_user(db_session, "tp01_user@t.com")
    team = await make_team(db_session, "tp01_Team")
    await make_membership(db_session, user.id, team.id)
    report = await make_weekly_report(db_session, user.id, PAST_WEEK)
    await make_admin_settings(db_session, team.id)

    with (
        patch(
            "app.services.graph_teams.refresh_graph_token",
            new=AsyncMock(return_value=("access-tok", "new-refresh")),
        ),
        patch(
            "app.services.graph_teams.post_channel_message",
            new=AsyncMock(),
        ) as mock_post,
    ):
        resp = await client.post(
            f"/api/v1/weekly-reports/{report.id}/teams-post",
            headers=auth(tok),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "posted"
    assert data["user_id"] == str(user.id)
    mock_post.assert_awaited_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["teams_team_id"] == "team-111"
    assert call_kwargs["teams_channel_id"] == "channel-222"


# ---------------------------------------------------------------------------
# 2. Idempotency: second call within 5-minute cooldown → 429
# ---------------------------------------------------------------------------


async def test_teams_post_cooldown(client, db_session):
    user, tok = await make_user(db_session, "tp02_user@t.com")
    team = await make_team(db_session, "tp02_Team")
    await make_membership(db_session, user.id, team.id)
    report = await make_weekly_report(db_session, user.id, PAST_WEEK)
    await make_admin_settings(db_session, team.id)

    # Pre-insert a TeamsPostRecord simulating a recent post
    idem_key = f"teams:{user.id}:{PAST_WEEK}"
    tpr = TeamsPostRecord(
        user_id=user.id,
        week_start=PAST_WEEK,
        idempotency_key=idem_key,
        status=TeamsPostStatus.posted,
        posted_at=datetime.now(UTC),
    )
    db_session.add(tpr)
    await db_session.commit()

    with patch(
        "app.services.graph_teams.post_channel_message",
        new=AsyncMock(),
    ) as mock_post:
        resp = await client.post(
            f"/api/v1/weekly-reports/{report.id}/teams-post",
            headers=auth(tok),
        )

    assert resp.status_code == 429
    mock_post.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3. Visibility: private fields are not included in the Teams message
# ---------------------------------------------------------------------------


async def test_teams_post_private_fields_excluded(client, db_session):
    user, tok = await make_user(db_session, "tp03_user@t.com")
    team = await make_team(db_session, "tp03_Team")
    await make_membership(db_session, user.id, team.id)
    # Include private-looking fields in report data; they must not reach the message
    report = await make_weekly_report(
        db_session,
        user.id,
        date(2026, 1, 12),
        data={
            "category_breakdown": {"Dev": 5},
            "day_load": 3,
            "blocker_text": "top-secret-blocker",
        },
    )
    await make_admin_settings(
        db_session, team.id, teams_team_id="t2", teams_channel_id="c2"
    )

    captured: dict = {}

    async def capture_post(**kwargs: object) -> None:
        captured.update(kwargs)

    with (
        patch(
            "app.services.graph_teams.refresh_graph_token",
            new=AsyncMock(return_value=("access-tok", "new-refresh")),
        ),
        patch(
            "app.services.graph_teams.post_channel_message",
            new=AsyncMock(side_effect=capture_post),
        ),
    ):
        resp = await client.post(
            f"/api/v1/weekly-reports/{report.id}/teams-post",
            headers=auth(tok),
        )

    assert resp.status_code == 200
    html_body: str = captured.get("html_body", "")
    assert "day_load" not in html_body
    assert "top-secret-blocker" not in html_body
    assert "blocker" not in html_body.lower()


# ---------------------------------------------------------------------------
# 4. Skip when Teams channel fields are NULL in AdminSettings → 422
# ---------------------------------------------------------------------------


async def test_teams_post_null_channel_config(client, db_session):
    user, tok = await make_user(db_session, "tp04_user@t.com")
    team = await make_team(db_session, "tp04_Team")
    await make_membership(db_session, user.id, team.id)
    report = await make_weekly_report(db_session, user.id, PAST_WEEK)
    await make_admin_settings(
        db_session, team.id, teams_team_id=None, teams_channel_id=None
    )

    with patch(
        "app.services.graph_teams.post_channel_message",
        new=AsyncMock(),
    ) as mock_post:
        resp = await client.post(
            f"/api/v1/weekly-reports/{report.id}/teams-post",
            headers=auth(tok),
        )

    assert resp.status_code == 422
    mock_post.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. Skip when no AdminSettings row exists → 422
# ---------------------------------------------------------------------------


async def test_teams_post_no_admin_settings(client, db_session):
    user, tok = await make_user(db_session, "tp05_user@t.com")
    team = await make_team(db_session, "tp05_Team")
    await make_membership(db_session, user.id, team.id)
    report = await make_weekly_report(db_session, user.id, PAST_WEEK)
    # Intentionally no AdminSettings row

    with patch(
        "app.services.graph_teams.post_channel_message",
        new=AsyncMock(),
    ) as mock_post:
        resp = await client.post(
            f"/api/v1/weekly-reports/{report.id}/teams-post",
            headers=auth(tok),
        )

    assert resp.status_code == 422
    mock_post.assert_not_awaited()


# ---------------------------------------------------------------------------
# 6. Scheduler integration: publish_teams_weekly_reports posts for active members
# ---------------------------------------------------------------------------


async def test_scheduler_publish_teams_weekly_reports(db_session):
    user, _ = await make_user(
        db_session, "tp06_user@t.com", refresh_token="sch-refresh"
    )
    team = await make_team(db_session, "tp06_Team")
    await make_membership(db_session, user.id, team.id)

    # week_start = today - 5 days (what the scheduler computes on a Saturday)
    week_start = date.today() - timedelta(days=5)
    # Normalise to Monday
    week_start = week_start - timedelta(days=week_start.weekday())
    await make_weekly_report(db_session, user.id, week_start)
    await make_admin_settings(
        db_session, team.id, teams_team_id="sch-team", teams_channel_id="sch-chan"
    )

    # Patch async_session_factory so the scheduler uses the test DB session
    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    with (
        patch(
            "app.services.graph_teams.refresh_graph_token",
            new=AsyncMock(return_value=("access-sch", "new-sch-refresh")),
        ),
        patch(
            "app.services.graph_teams.post_channel_message",
            new=AsyncMock(),
        ) as mock_post,
        patch(
            "app.core.scheduler.async_session_factory",
            new=fake_session_factory,
        ),
        patch("app.core.scheduler.date") as mock_date,
    ):
        saturday = week_start + timedelta(days=5)
        mock_date.today.return_value = saturday
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        await publish_teams_weekly_reports()

    mock_post.assert_awaited_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["teams_team_id"] == "sch-team"
    assert call_kwargs["teams_channel_id"] == "sch-chan"

    # TeamsPostRecord should be persisted with status=posted
    from sqlalchemy import select as sa_select

    tpr_r = await db_session.execute(
        sa_select(TeamsPostRecord).where(
            TeamsPostRecord.user_id == user.id,
            TeamsPostRecord.week_start == week_start,
        )
    )
    tpr = tpr_r.scalar_one_or_none()
    assert tpr is not None
    assert tpr.status == TeamsPostStatus.posted
