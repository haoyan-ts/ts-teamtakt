"""Tests for leader metrics endpoints (p11)."""

from datetime import UTC, date, datetime, timedelta

from app.core.security import create_access_token
from app.db.models.daily_record import DailyRecord
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_user(db, email, *, is_leader=False, is_admin=False):
    user = User(
        email=email,
        display_name=email.split("@")[0],
        is_leader=is_leader,
        is_admin=is_admin,
    )
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
    m = TeamMembership(
        user_id=user_id,
        team_id=team_id,
        joined_at=datetime.now(UTC),
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def make_record(db, user_id, record_date, day_load=3):
    rec = DailyRecord(
        user_id=user_id,
        record_date=record_date,
        day_load=day_load,
        form_opened_at=datetime.now(UTC),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Overload endpoint returns 200 for leader of team
# ---------------------------------------------------------------------------


async def test_overload_leader_can_access(client, db_session):
    leader, tok = await make_user(db_session, "m01_leader@t.com", is_leader=True)
    member, _ = await make_user(db_session, "m01_member@t.com")
    team = await make_team(db_session, "m01_Team")
    await make_membership(db_session, leader.id, team.id)
    await make_membership(db_session, member.id, team.id)

    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/overload",
        params={"start_date": str(start), "end_date": str(end)},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# 2. Non-leader member cannot access metrics
# ---------------------------------------------------------------------------


async def test_overload_member_forbidden(client, db_session):
    member, tok = await make_user(db_session, "m02_member@t.com")
    team = await make_team(db_session, "m02_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/overload",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=auth(tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. Overload streak detected: member at load=5 for 3+ consecutive days
# ---------------------------------------------------------------------------


async def test_overload_streak_detected(client, db_session):
    leader, tok = await make_user(db_session, "m03_leader@t.com", is_leader=True)
    member, _ = await make_user(db_session, "m03_member@t.com")
    team = await make_team(db_session, "m03_Team")
    await make_membership(db_session, leader.id, team.id)
    await make_membership(db_session, member.id, team.id)

    base = date(2026, 3, 2)  # Monday
    for i in range(5):
        await make_record(db_session, member.id, base + timedelta(days=i), day_load=5)

    # Set threshold to 4 so load=5 triggers overload
    await db_session.execute(
        __import__("sqlalchemy").text(
            f"UPDATE team_settings SET overload_load_threshold=4 WHERE team_id='{team.id}'"
        )
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/overload",
        params={"start_date": str(base), "end_date": str(base + timedelta(days=4))},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(e["user_id"] == str(member.id) for e in data)


# ---------------------------------------------------------------------------
# 4. Blocker summary endpoint accessible by leader
# ---------------------------------------------------------------------------


async def test_blocker_summary_leader(client, db_session):
    leader, tok = await make_user(db_session, "m04_leader@t.com", is_leader=True)
    team = await make_team(db_session, "m04_Team")
    await make_membership(db_session, leader.id, team.id)

    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/blockers",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "by_type" in body
    assert "recurring" in body


# ---------------------------------------------------------------------------
# 5. Fragmentation endpoint accessible by admin
# ---------------------------------------------------------------------------


async def test_fragmentation_admin(client, db_session):
    admin, tok = await make_user(db_session, "m05_admin@t.com", is_admin=True)
    team = await make_team(db_session, "m05_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/fragmentation",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# 6. Category balance endpoint returns list
# ---------------------------------------------------------------------------


async def test_category_balance_leader(client, db_session):
    leader, tok = await make_user(db_session, "m06_leader@t.com", is_leader=True)
    team = await make_team(db_session, "m06_Team")
    await make_membership(db_session, leader.id, team.id)

    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/balance",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "team_aggregate" in body
    assert "members" in body


# ---------------------------------------------------------------------------
# 7. Carry-over aging endpoint returns list
# ---------------------------------------------------------------------------


async def test_carryover_aging_leader(client, db_session):
    leader, tok = await make_user(db_session, "m07_leader@t.com", is_leader=True)
    team = await make_team(db_session, "m07_Team")
    await make_membership(db_session, leader.id, team.id)

    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/carryover-aging",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# 8. Project effort endpoint returns list
# ---------------------------------------------------------------------------


async def test_project_effort_leader(client, db_session):
    leader, tok = await make_user(db_session, "m08_leader@t.com", is_leader=True)
    team = await make_team(db_session, "m08_Team")
    await make_membership(db_session, leader.id, team.id)

    resp = await client.get(
        f"/api/v1/teams/{team.id}/metrics/project-effort",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
