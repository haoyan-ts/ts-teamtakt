"""Tests for daily record endpoints — focusing on visibility filtering (p06)."""

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


def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def insert_record(db, user_id, record_date, day_load=3):
    """Directly insert a DailyRecord bypassing the API (for past/locked dates)."""
    record = DailyRecord(
        user_id=user_id,
        record_date=record_date,
        day_load=day_load,
        form_opened_at=datetime.now(UTC),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# 1. Create daily record — success (owner sees day_load)
# ---------------------------------------------------------------------------


async def test_create_daily_record_ok(client, db_session):
    user, tok = await make_user(db_session, "dr01@t.com")
    team = await make_team(db_session, "dr01_team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 4,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["day_load"] == 4


# ---------------------------------------------------------------------------
# 2. Duplicate daily record rejected (409)
# ---------------------------------------------------------------------------


async def test_duplicate_daily_record_rejected(client, db_session):
    user, tok = await make_user(db_session, "dr02@t.com")
    team = await make_team(db_session, "dr02_team")
    await make_membership(db_session, user.id, team.id)

    for _ in range(2):
        resp = await client.post(
            "/api/v1/daily-records",
            json={
                "record_date": str(date.today()),
                "day_load": 2,
                "form_opened_at": datetime.now(UTC).isoformat(),
                "daily_work_logs": [],
            },
            headers=auth(tok),
        )

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 3. Visibility — owner always sees day_load
# ---------------------------------------------------------------------------


async def test_visibility_owner_sees_day_load(client, db_session):
    user, tok = await make_user(db_session, "dr03@t.com")
    team = await make_team(db_session, "dr03_team")
    await make_membership(db_session, user.id, team.id)

    # Use a distinct past date (directly inserted to bypass edit-window)
    rec_date = date.today() - timedelta(days=7)
    await insert_record(db_session, user.id, rec_date, day_load=5)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={user.id}",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    records = resp.json()
    target = next(r for r in records if r["record_date"] == str(rec_date))
    assert target["day_load"] == 5


# ---------------------------------------------------------------------------
# 4. Visibility — team leader sees day_load of team member
# ---------------------------------------------------------------------------


async def test_visibility_leader_sees_day_load(client, db_session):
    member, _ = await make_user(db_session, "dr04m@t.com")
    leader, leader_tok = await make_user(db_session, "dr04l@t.com", is_leader=True)
    team = await make_team(db_session, "dr04_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, leader.id, team.id)

    rec_date = date.today() - timedelta(days=8)
    await insert_record(db_session, member.id, rec_date, day_load=4)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={member.id}",
        headers=auth(leader_tok),
    )
    assert resp.status_code == 200
    records = resp.json()
    target = next(r for r in records if r["record_date"] == str(rec_date))
    assert target["day_load"] == 4  # leader has full visibility


# ---------------------------------------------------------------------------
# 5. Visibility — outsider (different team) cannot access records (403)
# ---------------------------------------------------------------------------


async def test_visibility_outsider_denied(client, db_session):
    member, _ = await make_user(db_session, "dr05m@t.com")
    outsider, outsider_tok = await make_user(db_session, "dr05o@t.com")
    team = await make_team(db_session, "dr05_team")
    outsider_team = await make_team(db_session, "dr05o_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, outsider.id, outsider_team.id)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={member.id}",
        headers=auth(outsider_tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 6. Visibility — non-leader querying other user's records (403)
# ---------------------------------------------------------------------------


async def test_visibility_non_leader_denied(client, db_session):
    member, _ = await make_user(db_session, "dr06m@t.com")
    peer, peer_tok = await make_user(db_session, "dr06p@t.com")  # not a leader
    team = await make_team(db_session, "dr06_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, peer.id, team.id)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={member.id}",
        headers=auth(peer_tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 7. Admin sees all records (200) with full visibility
# ---------------------------------------------------------------------------


async def test_visibility_admin_full_access(client, db_session):
    member, _ = await make_user(db_session, "dr07m@t.com")
    admin, admin_tok = await make_user(db_session, "dr07a@t.com", is_admin=True)
    team = await make_team(db_session, "dr07_team")
    admin_team = await make_team(db_session, "dr07a_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, admin.id, admin_team.id)

    rec_date = date.today() - timedelta(days=9)
    await insert_record(db_session, member.id, rec_date, day_load=2)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={member.id}",
        headers=auth(admin_tok),
    )
    assert resp.status_code == 200
    records = resp.json()
    target = next(r for r in records if r["record_date"] == str(rec_date))
    assert target["day_load"] == 2
