"""Tests for absence endpoints (p06)."""

from datetime import UTC, date, datetime, timedelta

from app.core.security import create_access_token
from app.db.models.absence import Absence
from app.db.models.daily_record import DailyRecord
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers (mirrors test_teams.py pattern)
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


def now_iso():
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# 1. Create absence — success
# ---------------------------------------------------------------------------


async def test_create_absence_ok(client, db_session):
    user, tok = await make_user(db_session, "abs01@t.com")
    team = await make_team(db_session, "abs01_team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.post(
        "/api/v1/absences",
        json={
            "record_date": str(date.today()),
            "absence_type": "holiday",
            "form_opened_at": now_iso(),
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["absence_type"] == "holiday"
    assert data["user_id"] == str(user.id)


# ---------------------------------------------------------------------------
# 2. Absence blocked when DailyRecord already exists for that date
# ---------------------------------------------------------------------------


async def test_absence_blocked_by_daily_record(client, db_session):
    user, tok = await make_user(db_session, "abs02@t.com")
    team = await make_team(db_session, "abs02_team")
    await make_membership(db_session, user.id, team.id)

    # Directly insert a DailyRecord to bypass edit-window API check
    record = DailyRecord(
        user_id=user.id,
        record_date=date.today(),
        day_load=3,
        form_opened_at=datetime.now(UTC),
    )
    db_session.add(record)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/absences",
        json={
            "record_date": str(date.today()),
            "absence_type": "illness",
            "form_opened_at": now_iso(),
        },
        headers=auth(tok),
    )
    assert resp.status_code == 409
    assert "daily record" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. DailyRecord blocked when Absence already exists for that date
# ---------------------------------------------------------------------------


async def test_daily_record_blocked_by_absence(client, db_session):
    user, tok = await make_user(db_session, "abs03@t.com")
    team = await make_team(db_session, "abs03_team")
    await make_membership(db_session, user.id, team.id)

    create_resp = await client.post(
        "/api/v1/absences",
        json={
            "record_date": str(date.today()),
            "absence_type": "holiday",
            "form_opened_at": now_iso(),
        },
        headers=auth(tok),
    )
    assert create_resp.status_code == 201

    dr_resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 3,
            "form_opened_at": now_iso(),
            "task_entries": [],
        },
        headers=auth(tok),
    )
    assert dr_resp.status_code == 409
    assert "absence" in dr_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Duplicate absence rejected (409)
# ---------------------------------------------------------------------------


async def test_duplicate_absence_rejected(client, db_session):
    user, tok = await make_user(db_session, "abs04@t.com")
    team = await make_team(db_session, "abs04_team")
    await make_membership(db_session, user.id, team.id)

    target_date = str(date.today() + timedelta(days=1))

    resp1 = await client.post(
        "/api/v1/absences",
        json={
            "record_date": target_date,
            "absence_type": "illness",
            "form_opened_at": now_iso(),
        },
        headers=auth(tok),
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/v1/absences",
        json={
            "record_date": target_date,
            "absence_type": "other",
            "form_opened_at": now_iso(),
        },
        headers=auth(tok),
    )
    assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# 5. List absences — own records
# ---------------------------------------------------------------------------


async def test_list_absences_own(client, db_session):
    user, tok = await make_user(db_session, "abs05@t.com")
    team = await make_team(db_session, "abs05_team")
    await make_membership(db_session, user.id, team.id)

    target_date = date.today() - timedelta(days=0)  # keep in open window
    # Insert directly to avoid edit-window check on list test setup
    absence = Absence(
        user_id=user.id,
        record_date=target_date,
        absence_type="holiday",
    )
    db_session.add(absence)
    await db_session.commit()

    resp = await client.get("/api/v1/absences", headers=auth(tok))
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert str(absence.id) in ids


# ---------------------------------------------------------------------------
# 6. List absences — leader can view team member's absences
# ---------------------------------------------------------------------------


async def test_list_absences_leader_access(client, db_session):
    member, member_tok = await make_user(db_session, "abs06m@t.com")
    leader, leader_tok = await make_user(db_session, "abs06l@t.com", is_leader=True)
    team = await make_team(db_session, "abs06_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, leader.id, team.id)

    absence = Absence(
        user_id=member.id, record_date=date.today(), absence_type="illness"
    )
    db_session.add(absence)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/absences?user_id={member.id}",
        headers=auth(leader_tok),
    )
    assert resp.status_code == 200
    assert any(a["id"] == str(absence.id) for a in resp.json())


# ---------------------------------------------------------------------------
# 7. Outsider cannot list another user's absences (403)
# ---------------------------------------------------------------------------


async def test_list_absences_outsider_denied(client, db_session):
    member, _ = await make_user(db_session, "abs07m@t.com")
    outsider, outsider_tok = await make_user(db_session, "abs07o@t.com")
    team = await make_team(db_session, "abs07_team")
    outsider_team = await make_team(db_session, "abs07o_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, outsider.id, outsider_team.id)

    resp = await client.get(
        f"/api/v1/absences?user_id={member.id}",
        headers=auth(outsider_tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 8. Update absence
# ---------------------------------------------------------------------------


async def test_update_absence(client, db_session):
    user, tok = await make_user(db_session, "abs08@t.com")
    team = await make_team(db_session, "abs08_team")
    await make_membership(db_session, user.id, team.id)

    create_resp = await client.post(
        "/api/v1/absences",
        json={
            "record_date": str(date.today()),
            "absence_type": "holiday",
            "form_opened_at": now_iso(),
        },
        headers=auth(tok),
    )
    assert create_resp.status_code == 201
    absence_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/v1/absences/{absence_id}",
        json={"absence_type": "illness", "form_opened_at": now_iso()},
        headers=auth(tok),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["absence_type"] == "illness"


# ---------------------------------------------------------------------------
# 9. Delete absence
# ---------------------------------------------------------------------------


async def test_delete_absence(client, db_session):
    user, tok = await make_user(db_session, "abs09@t.com")
    team = await make_team(db_session, "abs09_team")
    await make_membership(db_session, user.id, team.id)

    create_resp = await client.post(
        "/api/v1/absences",
        json={
            "record_date": str(date.today()),
            "absence_type": "other",
            "form_opened_at": now_iso(),
        },
        headers=auth(tok),
    )
    assert create_resp.status_code == 201
    absence_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/absences/{absence_id}",
        params={"form_opened_at": now_iso()},
        headers=auth(tok),
    )
    assert del_resp.status_code == 204

    # Confirm gone
    list_resp = await client.get("/api/v1/absences", headers=auth(tok))
    ids = [a["id"] for a in list_resp.json()]
    assert absence_id not in ids


# ---------------------------------------------------------------------------
# 10. Missing-days returns unreported working days
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 11. GET /absences/{absence_id} — detail endpoint
# ---------------------------------------------------------------------------


async def test_owner_gets_absence_detail(client, db_session):
    user, tok = await make_user(db_session, "abs11@t.com")
    team = await make_team(db_session, "abs11_team")
    await make_membership(db_session, user.id, team.id)

    target_date = date.today()
    absence = Absence(
        user_id=user.id,
        record_date=target_date,
        absence_type="holiday",
    )
    db_session.add(absence)
    await db_session.commit()
    await db_session.refresh(absence)

    resp = await client.get(f"/api/v1/absences/{absence.id}", headers=auth(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(absence.id)
    assert data["record_date"] == str(target_date)


async def test_leader_gets_team_member_absence_detail(client, db_session):
    leader, leader_tok = await make_user(db_session, "abs12l@t.com", is_leader=True)
    member, _ = await make_user(db_session, "abs12m@t.com")
    team = await make_team(db_session, "abs12_team")
    await make_membership(db_session, leader.id, team.id)
    await make_membership(db_session, member.id, team.id)

    absence = Absence(
        user_id=member.id,
        record_date=date.today() - timedelta(days=1),
        absence_type="illness",
    )
    db_session.add(absence)
    await db_session.commit()
    await db_session.refresh(absence)

    resp = await client.get(f"/api/v1/absences/{absence.id}", headers=auth(leader_tok))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(absence.id)


async def test_get_absence_detail_not_found(client, db_session):
    user, tok = await make_user(db_session, "abs13@t.com")
    team = await make_team(db_session, "abs13_team")
    await make_membership(db_session, user.id, team.id)
    import uuid

    resp = await client.get(f"/api/v1/absences/{uuid.uuid4()}", headers=auth(tok))
    assert resp.status_code == 404


async def test_outsider_cannot_get_absence_detail(client, db_session):
    owner, _ = await make_user(db_session, "abs14o@t.com")
    outsider, outsider_tok = await make_user(db_session, "abs14x@t.com")
    owner_team = await make_team(db_session, "abs14o_team")
    outsider_team = await make_team(db_session, "abs14x_team")
    await make_membership(db_session, owner.id, owner_team.id)
    await make_membership(db_session, outsider.id, outsider_team.id)

    absence = Absence(
        user_id=owner.id,
        record_date=date.today() - timedelta(days=2),
        absence_type="other",
    )
    db_session.add(absence)
    await db_session.commit()
    await db_session.refresh(absence)

    resp = await client.get(
        f"/api/v1/absences/{absence.id}", headers=auth(outsider_tok)
    )
    assert resp.status_code == 403


async def test_missing_days_basic(client, db_session):
    user, tok = await make_user(db_session, "abs10@t.com")
    team = await make_team(db_session, "abs10_team")
    await make_membership(db_session, user.id, team.id)

    # Use Mon–Fri of last week (always closed window — insert directly)
    today = date.today()
    # Find last Monday
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_friday = last_monday + timedelta(days=4)

    # Create a record for Tuesday of last week
    last_tuesday = last_monday + timedelta(days=1)
    record = DailyRecord(
        user_id=user.id,
        record_date=last_tuesday,
        day_load=2,
        form_opened_at=datetime.now(UTC),
    )
    db_session.add(record)

    # Create an absence for Wednesday of last week
    last_wednesday = last_monday + timedelta(days=2)
    absence = Absence(
        user_id=user.id,
        record_date=last_wednesday,
        absence_type="holiday",
    )
    db_session.add(absence)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/missing-days",
        params={
            "start_date": str(last_monday),
            "end_date": str(last_friday),
        },
        headers=auth(tok),
    )
    assert resp.status_code == 200
    missing = resp.json()

    # Mon, Thu, Fri should be missing (Tue reported, Wed absent)
    assert str(last_monday) in missing
    assert str(last_tuesday) not in missing  # reported
    assert str(last_wednesday) not in missing  # absent
    last_thursday = last_monday + timedelta(days=3)
    assert str(last_thursday) in missing
    assert str(last_friday) in missing
