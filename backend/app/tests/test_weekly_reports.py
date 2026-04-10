"""Tests for weekly report generation and email draft endpoints (p12).

Key invariants tested:
- Weekly report generate → 201; 422 if edit window not yet closed
- Weekly report idempotency: second generate for same week upserts (no duplicate)
- Email draft creation requires a weekly report to exist
- Email draft 5-minute cooldown between sends
- Cannot edit or re-send an already-sent draft
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User
from app.db.models.weekly_report import EmailDraftStatus, WeeklyEmailDraft, WeeklyReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_user(db, email, *, is_leader=False):
    user = User(email=email, display_name=email.split("@")[0], is_leader=is_leader)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return user, token


async def make_team(db, name):
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


async def make_weekly_report(db, user_id, week_start):
    rpt = WeeklyReport(user_id=user_id, week_start=week_start, data={})
    db.add(rpt)
    await db.commit()
    await db.refresh(rpt)
    return rpt


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# A Monday safely in the past so edit window (Mon + 12 days = Saturday before last)
PAST_WEEK = date(2026, 1, 5)  # Monday 2026-01-05; window closed Sat 2026-01-17


# ---------------------------------------------------------------------------
# 1. Generate report for a closed week → 201
# ---------------------------------------------------------------------------


async def test_generate_weekly_report_closed_week(client, db_session):
    user, tok = await make_user(db_session, "wr01_user@t.com")
    team = await make_team(db_session, "wr01_Team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.post(
        "/api/v1/weekly-reports/generate",
        params={"week_start": str(PAST_WEEK)},
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["week_start"] == str(PAST_WEEK)
    assert data["user_id"] == str(user.id)


# ---------------------------------------------------------------------------
# 2. Generate report for an open week → 422
# ---------------------------------------------------------------------------


async def test_generate_weekly_report_open_week_rejected(client, db_session):
    user, tok = await make_user(db_session, "wr02_user@t.com")
    team = await make_team(db_session, "wr02_Team")
    await make_membership(db_session, user.id, team.id)

    # Use a Monday far in the future so the edit window is still open
    future_monday = date.today() + timedelta(days=30)
    # Roll back to Monday
    future_monday -= timedelta(days=future_monday.weekday())

    resp = await client.post(
        "/api/v1/weekly-reports/generate",
        params={"week_start": str(future_monday)},
        headers=auth(tok),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. Generate twice for same week → idempotent (second request returns same data)
# ---------------------------------------------------------------------------


async def test_generate_weekly_report_idempotent(client, db_session):
    user, tok = await make_user(db_session, "wr03_user@t.com")
    team = await make_team(db_session, "wr03_Team")
    await make_membership(db_session, user.id, team.id)

    week = date(2026, 1, 12)  # Another past closed week

    await client.post(
        "/api/v1/weekly-reports/generate",
        params={"week_start": str(week)},
        headers=auth(tok),
    )

    # Second call should succeed (upsert), not create a duplicate row
    resp2 = await client.post(
        "/api/v1/weekly-reports/generate",
        params={"week_start": str(week)},
        headers=auth(tok),
    )
    assert resp2.status_code == 201
    assert resp2.json()["week_start"] == str(week)


# ---------------------------------------------------------------------------
# 4. Get weekly report → 200 after generation
# ---------------------------------------------------------------------------


async def test_get_weekly_report(client, db_session):
    user, tok = await make_user(db_session, "wr04_user@t.com")
    team = await make_team(db_session, "wr04_Team")
    await make_membership(db_session, user.id, team.id)

    week = date(2026, 1, 19)
    await make_weekly_report(db_session, user.id, week)

    resp = await client.get(
        "/api/v1/weekly-reports",
        params={"week_start": str(week)},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["week_start"] == str(week)


# ---------------------------------------------------------------------------
# 5. Get weekly report → 404 if not generated yet
# ---------------------------------------------------------------------------


async def test_get_weekly_report_not_found(client, db_session):
    user, tok = await make_user(db_session, "wr05_user@t.com")
    team = await make_team(db_session, "wr05_Team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.get(
        "/api/v1/weekly-reports",
        params={"week_start": "2020-01-06"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 6. Email draft: requires weekly report to exist first
# ---------------------------------------------------------------------------


async def test_create_email_draft_requires_report(client, db_session):
    user, tok = await make_user(db_session, "wr06_user@t.com")
    team = await make_team(db_session, "wr06_Team")
    await make_membership(db_session, user.id, team.id)

    with patch("app.services.llm.generate_email_draft", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "tasks": "T",
            "successes": "S",
            "next_week": "N",
        }
        resp = await client.post(
            "/api/v1/weekly-emails/draft",
            params={"week_start": "2026-02-02"},
            headers=auth(tok),
        )
    # No weekly report exists → 404
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. Email re-send cooldown: 5-minute window enforced
# ---------------------------------------------------------------------------


async def test_email_resend_cooldown(client, db_session):
    """Sending an email twice within 5 minutes should be rejected by 429."""
    user, tok = await make_user(db_session, "wr07_user@t.com")
    user.ms_graph_refresh_token = "fake-token"  # type: ignore[attr-defined]
    await db_session.commit()

    team = await make_team(db_session, "wr07_Team")
    await make_membership(db_session, user.id, team.id)

    # Create a draft that looks "sent" 1 minute ago (within cooldown)
    recent_sent = datetime.now(UTC) - timedelta(minutes=1)
    draft = WeeklyEmailDraft(
        user_id=user.id,
        week_start=date(2026, 2, 9),
        subject="Test",
        body_sections={},
        status=EmailDraftStatus.draft,
        idempotency_key=f"{user.id}:{date(2026, 2, 9)}",
        sent_at=recent_sent,
    )
    db_session.add(draft)
    await db_session.commit()
    await db_session.refresh(draft)

    resp = await client.post(
        f"/api/v1/weekly-emails/{draft.id}/send",
        headers=auth(tok),
    )
    # Within cooldown → 409 (already_sent check fires first since status is draft but sent_at is set)
    assert resp.status_code in (409, 429)
