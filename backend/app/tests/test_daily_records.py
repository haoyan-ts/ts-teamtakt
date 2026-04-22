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


async def insert_record(db, user_id, record_date, day_load=80):
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
            "day_load": 80,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["day_load"] == 80


# ---------------------------------------------------------------------------
# 2. Duplicate daily record rejected (409)
# ---------------------------------------------------------------------------


async def test_duplicate_daily_record_rejected(client, db_session):
    user, tok = await make_user(db_session, "dr02@t.com")
    team = await make_team(db_session, "dr02_team")
    await make_membership(db_session, user.id, team.id)

    payload = {
        "record_date": str(date.today()),
        "day_load": 50,
        "form_opened_at": datetime.now(UTC).isoformat(),
        "daily_work_logs": [],
    }
    await client.post("/api/v1/daily-records", json=payload, headers=auth(tok))
    resp = await client.post("/api/v1/daily-records", json=payload, headers=auth(tok))

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
    await insert_record(db_session, user.id, rec_date, day_load=75)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={user.id}",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    records = resp.json()
    target = next(r for r in records if r["record_date"] == str(rec_date))
    assert target["day_load"] == 75


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
    await insert_record(db_session, member.id, rec_date, day_load=80)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={member.id}",
        headers=auth(leader_tok),
    )
    assert resp.status_code == 200
    records = resp.json()
    target = next(r for r in records if r["record_date"] == str(rec_date))
    assert target["day_load"] == 80  # leader has full visibility


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
    await insert_record(db_session, member.id, rec_date, day_load=50)

    resp = await client.get(
        f"/api/v1/daily-records?user_id={member.id}",
        headers=auth(admin_tok),
    )
    assert resp.status_code == 200
    records = resp.json()
    target = next(r for r in records if r["record_date"] == str(rec_date))
    assert target["day_load"] == 50


# ---------------------------------------------------------------------------
# 8. GET /daily-records/{record_id} — detail endpoint
# ---------------------------------------------------------------------------


async def test_owner_gets_record_detail(client, db_session):
    user, tok = await make_user(db_session, "dr08@t.com")
    team = await make_team(db_session, "dr08_team")
    await make_membership(db_session, user.id, team.id)

    rec_date = date.today() - timedelta(days=10)
    record = await insert_record(db_session, user.id, rec_date, day_load=80)

    resp = await client.get(f"/api/v1/daily-records/{record.id}", headers=auth(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(record.id)
    assert data["day_load"] == 80


async def test_leader_gets_record_detail_with_day_load(client, db_session):
    leader, leader_tok = await make_user(db_session, "dr09l@t.com", is_leader=True)
    member, _ = await make_user(db_session, "dr09m@t.com")
    team = await make_team(db_session, "dr09_team")
    await make_membership(db_session, leader.id, team.id)
    await make_membership(db_session, member.id, team.id)

    rec_date = date.today() - timedelta(days=11)
    record = await insert_record(db_session, member.id, rec_date, day_load=75)

    resp = await client.get(
        f"/api/v1/daily-records/{record.id}", headers=auth(leader_tok)
    )
    assert resp.status_code == 200
    assert resp.json()["day_load"] == 75


async def test_get_record_detail_not_found(client, db_session):
    user, tok = await make_user(db_session, "dr10@t.com")
    team = await make_team(db_session, "dr10_team")
    await make_membership(db_session, user.id, team.id)
    import uuid

    resp = await client.get(f"/api/v1/daily-records/{uuid.uuid4()}", headers=auth(tok))
    assert resp.status_code == 404


async def test_outsider_cannot_get_record_detail(client, db_session):
    owner, _ = await make_user(db_session, "dr11o@t.com")
    outsider, outsider_tok = await make_user(db_session, "dr11x@t.com")
    team = await make_team(db_session, "dr11o_team")
    other_team = await make_team(db_session, "dr11x_team")
    await make_membership(db_session, owner.id, team.id)
    await make_membership(db_session, outsider.id, other_team.id)

    rec_date = date.today() - timedelta(days=12)
    record = await insert_record(db_session, owner.id, rec_date)

    resp = await client.get(
        f"/api/v1/daily-records/{record.id}", headers=auth(outsider_tok)
    )
    assert resp.status_code == 403


async def test_non_leader_peer_cannot_get_record_detail(client, db_session):
    owner, _ = await make_user(db_session, "dr12o@t.com")
    peer, peer_tok = await make_user(db_session, "dr12p@t.com")
    team = await make_team(db_session, "dr12_team")
    await make_membership(db_session, owner.id, team.id)
    await make_membership(db_session, peer.id, team.id)

    rec_date = date.today() - timedelta(days=13)
    record = await insert_record(db_session, owner.id, rec_date)

    resp = await client.get(
        f"/api/v1/daily-records/{record.id}", headers=auth(peer_tok)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Fibonacci effort validation — DailyWorkLog.effort
# ---------------------------------------------------------------------------


def _work_log_payload(task_id: str, effort: int, **overrides):
    base = {
        "task_id": task_id,
        "effort": effort,
        "energy_type": None,
        "insight": None,
        "blocker_text": None,
        "sort_order": 0,
        "self_assessment_tags": [],
    }
    base.update(overrides)
    return base


async def test_work_log_non_fibonacci_effort_rejected(client, db_session):
    """Pydantic rejects effort values not in {1,2,3,5,8} before any DB access."""
    user, tok = await make_user(db_session, "fib10@t.com")
    team = await make_team(db_session, "fib10_team")
    await make_membership(db_session, user.id, team.id)

    import uuid

    fake_task_id = str(uuid.uuid4())
    for invalid in (4, 6, 7):
        resp = await client.post(
            "/api/v1/daily-records",
            json={
                "record_date": str(date.today()),
                "day_load": 80,
                "form_opened_at": datetime.now(UTC).isoformat(),
                "daily_work_logs": [_work_log_payload(fake_task_id, invalid)],
            },
            headers=auth(tok),
        )
        assert resp.status_code == 422, f"effort={invalid} should be rejected"


async def test_work_log_effort_eight_accepted_schema(client, db_session):
    """effort=8 must pass Pydantic schema validation (422 would be a schema rejection)."""
    user, tok = await make_user(db_session, "fib11@t.com")
    team = await make_team(db_session, "fib11_team")
    await make_membership(db_session, user.id, team.id)

    import uuid

    fake_task_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 80,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [_work_log_payload(fake_task_id, 8)],
        },
        headers=auth(tok),
    )
    # May fail for reasons other than schema (e.g. task not found), but must NOT be 422
    assert resp.status_code != 422, "effort=8 should pass Pydantic validation"


async def test_work_log_invalid_energy_type_rejected(client, db_session):
    """energy_type values outside the allowed enum are rejected with 422."""
    user, tok = await make_user(db_session, "fib12@t.com")
    team = await make_team(db_session, "fib12_team")
    await make_membership(db_session, user.id, team.id)

    import uuid

    fake_task_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 80,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [
                _work_log_payload(fake_task_id, 3, energy_type="unknown_type")
            ],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 422


async def test_work_log_valid_energy_type_accepted_schema(client, db_session):
    """Valid energy_type values pass Pydantic schema validation."""
    user, tok = await make_user(db_session, "fib13@t.com")
    team = await make_team(db_session, "fib13_team")
    await make_membership(db_session, user.id, team.id)

    import uuid

    fake_task_id = str(uuid.uuid4())
    for energy in ("deep_focus", "collaborative", "admin", "creative", "reactive"):
        resp = await client.post(
            "/api/v1/daily-records",
            json={
                "record_date": str(date.today()),
                "day_load": 80,
                "form_opened_at": datetime.now(UTC).isoformat(),
                "daily_work_logs": [
                    _work_log_payload(fake_task_id, 3, energy_type=energy)
                ],
            },
            headers=auth(tok),
        )
        assert (
            resp.status_code != 422
        ), f"energy_type={energy!r} should pass schema validation"


# ---------------------------------------------------------------------------
# day_load battery % boundary validation
# ---------------------------------------------------------------------------


async def test_day_load_zero_accepted(client, db_session):
    """day_load=0 (0% battery) must be accepted."""
    user, tok = await make_user(db_session, "dl_boundary01@t.com")
    team = await make_team(db_session, "dl_boundary01_team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 0,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["day_load"] == 0


async def test_day_load_hundred_accepted(client, db_session):
    """day_load=100 (100% battery) must be accepted."""
    user, tok = await make_user(db_session, "dl_boundary02@t.com")
    team = await make_team(db_session, "dl_boundary02_team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 100,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["day_load"] == 100


async def test_day_load_negative_rejected(client, db_session):
    """day_load=-1 must be rejected with 422."""
    user, tok = await make_user(db_session, "dl_boundary03@t.com")
    team = await make_team(db_session, "dl_boundary03_team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": -1,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 422


async def test_day_load_over_hundred_rejected(client, db_session):
    """day_load=101 must be rejected with 422."""
    user, tok = await make_user(db_session, "dl_boundary04@t.com")
    team = await make_team(db_session, "dl_boundary04_team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 101,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /daily-records/breakdown — effort breakdown by energy type
# ---------------------------------------------------------------------------


async def insert_record_with_logs(db, user_id, record_date, day_load, logs):
    """Insert a DailyRecord and DailyWorkLog rows directly for testing."""
    from app.db.models.task import DailyWorkLog

    record = DailyRecord(
        user_id=user_id,
        record_date=record_date,
        day_load=day_load,
        form_opened_at=datetime.now(UTC),
    )
    db.add(record)
    await db.flush()
    for log_data in logs:
        db.add(
            DailyWorkLog(
                daily_record_id=record.id,
                task_id=log_data["task_id"],
                effort=log_data["effort"],
                energy_type=log_data.get("energy_type"),
                sort_order=log_data.get("sort_order", 0),
            )
        )
    await db.commit()
    await db.refresh(record)
    return record


async def test_breakdown_owner_sees_battery_pct(client, db_session):
    """Owner receives battery_pct in their own breakdown."""
    import uuid

    user, tok = await make_user(db_session, "bd01@t.com")
    team = await make_team(db_session, "bd01_team")
    await make_membership(db_session, user.id, team.id)

    rec_date = date.today() - timedelta(days=20)
    fake_task_id = uuid.uuid4()
    await insert_record_with_logs(
        db_session,
        user.id,
        rec_date,
        day_load=65,
        logs=[
            {"task_id": fake_task_id, "effort": 3, "energy_type": "deep_focus"},
            {"task_id": uuid.uuid4(), "effort": 2, "energy_type": "admin"},
        ],
    )

    resp = await client.get(
        f"/api/v1/daily-records/breakdown?date={rec_date}&user_id={user.id}",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_effort"] == 5
    assert data["battery_pct"] == 65
    by_type = {e["energy_type"]: e["effort"] for e in data["by_energy_type"]}
    assert by_type["deep_focus"] == 3
    assert by_type["admin"] == 2


async def test_breakdown_leader_sees_battery_pct(client, db_session):
    """Team leader can see battery_pct for a member."""
    import uuid

    member, _ = await make_user(db_session, "bd02m@t.com")
    leader, leader_tok = await make_user(db_session, "bd02l@t.com", is_leader=True)
    team = await make_team(db_session, "bd02_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, leader.id, team.id)

    rec_date = date.today() - timedelta(days=21)
    await insert_record_with_logs(
        db_session,
        member.id,
        rec_date,
        day_load=80,
        logs=[{"task_id": uuid.uuid4(), "effort": 5, "energy_type": "collaborative"}],
    )

    resp = await client.get(
        f"/api/v1/daily-records/breakdown?date={rec_date}&user_id={member.id}",
        headers=auth(leader_tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["battery_pct"] == 80
    assert data["total_effort"] == 5


async def test_breakdown_outsider_denied(client, db_session):
    """Non-leader peer cannot view another user's breakdown."""

    member, _ = await make_user(db_session, "bd03m@t.com")
    outsider, outsider_tok = await make_user(db_session, "bd03x@t.com")
    team = await make_team(db_session, "bd03_team")
    other_team = await make_team(db_session, "bd03x_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, outsider.id, other_team.id)

    rec_date = date.today() - timedelta(days=22)
    await insert_record_with_logs(db_session, member.id, rec_date, day_load=50, logs=[])

    resp = await client.get(
        f"/api/v1/daily-records/breakdown?date={rec_date}&user_id={member.id}",
        headers=auth(outsider_tok),
    )
    assert resp.status_code == 403


async def test_breakdown_battery_pct_hidden_from_peer(client, db_session):
    """Non-leader same-team peer cannot read another user's breakdown."""

    member, _ = await make_user(db_session, "bd04m@t.com")
    peer, peer_tok = await make_user(db_session, "bd04p@t.com")
    team = await make_team(db_session, "bd04_team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, peer.id, team.id)

    rec_date = date.today() - timedelta(days=23)
    await insert_record_with_logs(db_session, member.id, rec_date, day_load=40, logs=[])

    resp = await client.get(
        f"/api/v1/daily-records/breakdown?date={rec_date}&user_id={member.id}",
        headers=auth(peer_tok),
    )
    assert resp.status_code == 403


async def test_breakdown_no_record_returns_zeros(client, db_session):
    """Breakdown for a date with no record returns total_effort=0 and empty list."""
    user, tok = await make_user(db_session, "bd05@t.com")
    team = await make_team(db_session, "bd05_team")
    await make_membership(db_session, user.id, team.id)

    rec_date = date.today() - timedelta(days=100)
    resp = await client.get(
        f"/api/v1/daily-records/breakdown?date={rec_date}",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_effort"] == 0
    assert data["by_energy_type"] == []
    assert data["battery_pct"] is None


async def test_breakdown_null_energy_type_grouped(client, db_session):
    """Work logs with energy_type=None appear as null key in by_energy_type."""
    import uuid

    user, tok = await make_user(db_session, "bd06@t.com")
    team = await make_team(db_session, "bd06_team")
    await make_membership(db_session, user.id, team.id)

    rec_date = date.today() - timedelta(days=24)
    await insert_record_with_logs(
        db_session,
        user.id,
        rec_date,
        day_load=70,
        logs=[
            {"task_id": uuid.uuid4(), "effort": 1, "energy_type": None},
            {"task_id": uuid.uuid4(), "effort": 2, "energy_type": None},
        ],
    )

    resp = await client.get(
        f"/api/v1/daily-records/breakdown?date={rec_date}",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_effort"] == 3
    null_entry = next(
        (e for e in data["by_energy_type"] if e["energy_type"] is None), None
    )
    assert null_entry is not None
    assert null_entry["effort"] == 3


async def test_breakdown_total_effort_is_fibonacci_sum(client, db_session):
    """Total effort is the integer sum of Fibonacci effort values — no conversion."""
    import uuid

    user, tok = await make_user(db_session, "bd07@t.com")
    team = await make_team(db_session, "bd07_team")
    await make_membership(db_session, user.id, team.id)

    rec_date = date.today() - timedelta(days=25)
    await insert_record_with_logs(
        db_session,
        user.id,
        rec_date,
        day_load=55,
        logs=[
            {"task_id": uuid.uuid4(), "effort": 1, "energy_type": "deep_focus"},
            {"task_id": uuid.uuid4(), "effort": 2, "energy_type": "deep_focus"},
            {"task_id": uuid.uuid4(), "effort": 5, "energy_type": "reactive"},
            {"task_id": uuid.uuid4(), "effort": 8, "energy_type": "reactive"},
        ],
    )

    resp = await client.get(
        f"/api/v1/daily-records/breakdown?date={rec_date}",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_effort"] == 16  # 1+2+5+8
    by_type = {e["energy_type"]: e["effort"] for e in data["by_energy_type"]}
    assert by_type["deep_focus"] == 3  # 1+2
    assert by_type["reactive"] == 13  # 5+8


# ---------------------------------------------------------------------------
# is_primary validation — self-assessment tags
# ---------------------------------------------------------------------------


async def _create_task_and_tag(db, user_id):
    """Helper: insert a Task and a SelfAssessmentTag directly, return their IDs."""
    import uuid as _uuid

    from sqlalchemy import select

    from app.db.models.category import Category, SelfAssessmentTag
    from app.db.models.task import Task

    # Ensure we have a category
    existing_cat = (
        await db.execute(select(Category).where(Category.name == "is_primary_cat"))
    ).scalar_one_or_none()
    if existing_cat is None:
        cat = Category(
            id=_uuid.uuid4(), name="is_primary_cat", is_active=True, sort_order=99
        )
        db.add(cat)
        await db.flush()
        cat_id = cat.id
    else:
        cat_id = existing_cat.id

    # Ensure we have a self-assessment tag
    existing_tag = (
        await db.execute(
            select(SelfAssessmentTag).where(SelfAssessmentTag.name == "OKR")
        )
    ).scalar_one_or_none()
    if existing_tag is None:
        tag = SelfAssessmentTag(id=_uuid.uuid4(), name="OKR", is_active=True)
        db.add(tag)
        await db.flush()
        tag_id = tag.id
    else:
        tag_id = existing_tag.id

    task = Task(
        id=_uuid.uuid4(),
        title="is_primary test task",
        assignee_id=user_id,
        created_by=user_id,
        category_id=cat_id,
        status="todo",
        is_active=True,
    )
    db.add(task)
    await db.commit()
    return str(task.id), str(tag_id)


async def test_work_log_zero_primary_tags_rejected(client, db_session):
    """Submitting a work log with no primary tag (is_primary=False for all) → 422."""
    user, tok = await make_user(db_session, "isprim01@t.com")
    team = await make_team(db_session, "isprim01_team")
    await make_membership(db_session, user.id, team.id)
    task_id, tag_id = await _create_task_and_tag(db_session, user.id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 80,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [
                _work_log_payload(
                    task_id,
                    3,
                    self_assessment_tags=[
                        {"self_assessment_tag_id": tag_id, "is_primary": False}
                    ],
                )
            ],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 400


async def test_work_log_multiple_primary_tags_rejected(client, db_session):
    """Submitting a work log with >1 primary tag → 422."""
    import uuid

    from sqlalchemy import select

    from app.db.models.category import SelfAssessmentTag

    user, tok = await make_user(db_session, "isprim02@t.com")
    team = await make_team(db_session, "isprim02_team")
    await make_membership(db_session, user.id, team.id)
    task_id, tag_id = await _create_task_and_tag(db_session, user.id)

    # Get a second tag
    result = await db_session.execute(
        select(SelfAssessmentTag).where(SelfAssessmentTag.is_active.is_(True)).limit(2)
    )
    tags = result.scalars().all()
    if len(tags) < 2:
        second_tag = SelfAssessmentTag(
            id=uuid.uuid4(), name="Routine_isprim02", is_active=True
        )
        db_session.add(second_tag)
        await db_session.commit()
        second_tag_id = str(second_tag.id)
    else:
        second_tag_id = str(tags[1].id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 80,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [
                _work_log_payload(
                    task_id,
                    3,
                    self_assessment_tags=[
                        {"self_assessment_tag_id": tag_id, "is_primary": True},
                        {"self_assessment_tag_id": second_tag_id, "is_primary": True},
                    ],
                )
            ],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 400


async def test_work_log_exactly_one_primary_tag_accepted(client, db_session):
    """Submitting a work log with exactly one is_primary=True tag → 201."""
    import uuid

    from sqlalchemy import select

    from app.db.models.category import SelfAssessmentTag

    user, tok = await make_user(db_session, "isprim03@t.com")
    team = await make_team(db_session, "isprim03_team")
    await make_membership(db_session, user.id, team.id)
    task_id, tag_id = await _create_task_and_tag(db_session, user.id)

    result = await db_session.execute(
        select(SelfAssessmentTag).where(SelfAssessmentTag.is_active.is_(True)).limit(2)
    )
    tags = result.scalars().all()
    if len(tags) < 2:
        second_tag = SelfAssessmentTag(
            id=uuid.uuid4(), name="Routine_isprim03", is_active=True
        )
        db_session.add(second_tag)
        await db_session.commit()
        second_tag_id = str(second_tag.id)
    else:
        second_tag_id = str(tags[1].id)

    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 80,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [
                _work_log_payload(
                    task_id,
                    3,
                    self_assessment_tags=[
                        {"self_assessment_tag_id": tag_id, "is_primary": True},
                        {"self_assessment_tag_id": second_tag_id, "is_primary": False},
                    ],
                )
            ],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Check / uncheck toggle
# ---------------------------------------------------------------------------


async def _create_record_today(client, db_session, email_suffix):
    user, tok = await make_user(db_session, f"{email_suffix}@t.com")
    team = await make_team(db_session, f"{email_suffix}_team")
    await make_membership(db_session, user.id, team.id)
    resp = await client.post(
        "/api/v1/daily-records",
        json={
            "record_date": str(date.today()),
            "day_load": 70,
            "form_opened_at": datetime.now(UTC).isoformat(),
            "daily_work_logs": [],
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    return user, tok, resp.json()["id"]


async def test_check_record_within_window(client, db_session):
    """POST /check within edit window → 200, is_checked=True, is_locked=True."""
    _, tok, record_id = await _create_record_today(client, db_session, "chk01")
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_checked"] is True
    assert data["is_locked"] is True


async def test_uncheck_record_within_window(client, db_session):
    """DELETE /check within edit window → 200, is_checked=False; sent_at untouched."""
    _, tok, record_id = await _create_record_today(client, db_session, "unchk01")
    r = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert r.status_code == 200
    resp = await client.request(
        "DELETE",
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_checked"] is False
    assert data["teams_message_sent_at"] is None
    assert data["email_sent_at"] is None


async def test_check_outside_window_no_grant(client, db_session):
    """Check on a past-window record without unlock grant → 423."""
    user, tok = await make_user(db_session, "chk_ow01@t.com")
    team = await make_team(db_session, "chk_ow01_team")
    await make_membership(db_session, user.id, team.id)
    past_date = date.today() - timedelta(days=21)
    record = await insert_record(db_session, user.id, past_date)
    resp = await client.post(
        f"/api/v1/daily-records/{record.id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert resp.status_code == 423


async def test_check_outside_window_with_grant(client, db_session):
    """Check on a past-window record WITH an active unlock grant → 200."""
    from app.db.models.grants import UnlockGrant

    user, tok = await make_user(db_session, "chk_grant01@t.com")
    leader, _ = await make_user(db_session, "chk_leader01@t.com", is_leader=True)
    team = await make_team(db_session, "chk_grant01_team")
    await make_membership(db_session, user.id, team.id)
    await make_membership(db_session, leader.id, team.id)

    past_date = date.today() - timedelta(days=21)
    record = await insert_record(db_session, user.id, past_date)

    grant = UnlockGrant(user_id=user.id, record_date=past_date, granted_by=leader.id)
    db_session.add(grant)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/daily-records/{record.id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert resp.json()["is_checked"] is True


async def test_check_stale_form_opened_at(client, db_session):
    """form_opened_at older than 6 hours → 423."""
    _, tok, record_id = await _create_record_today(client, db_session, "chk_stale01")
    stale_ts = (datetime.now(UTC) - timedelta(hours=7)).isoformat()
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": stale_ts},
        headers=auth(tok),
    )
    assert resp.status_code == 423


async def test_check_other_user_forbidden(client, db_session):
    """Attempting to check another user's record → 403."""
    _, _tok, record_id = await _create_record_today(client, db_session, "chk_own01")
    other, other_tok = await make_user(db_session, "chk_own02@t.com")
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(other_tok),
    )
    assert resp.status_code == 403


async def test_uncheck_does_not_clear_sent_at(client, db_session):
    """Un-check after teams_message_sent_at is set should not clear it."""
    import uuid as _uuid

    from sqlalchemy import select as sa_select

    from app.db.models.daily_record import DailyRecord as DR

    _, tok, record_id = await _create_record_today(client, db_session, "unchk_sent01")
    r = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert r.status_code == 200
    rid = _uuid.UUID(record_id)
    record = await db_session.scalar(sa_select(DR).where(DR.id == rid))
    assert record is not None
    record.teams_message_sent_at = datetime.now(UTC)
    await db_session.commit()
    resp = await client.request(
        "DELETE",
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert resp.json()["is_checked"] is False
    assert resp.json()["teams_message_sent_at"] is not None


# ---------------------------------------------------------------------------
# Draft endpoints
# ---------------------------------------------------------------------------


async def test_get_teams_draft_returns_record_fields(client, db_session):
    """GET teams-message/draft returns subject with user name and record date."""
    _, tok, record_id = await _create_record_today(client, db_session, "draft01")
    resp = await client.get(
        f"/api/v1/daily-records/{record_id}/teams-message/draft",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "subject" in data
    assert "body" in data
    assert str(date.today()) in data["subject"]


async def test_get_email_draft_returns_record_fields(client, db_session):
    """GET email/draft returns subject with user name and record date."""
    _, tok, record_id = await _create_record_today(client, db_session, "draft02")
    resp = await client.get(
        f"/api/v1/daily-records/{record_id}/email/draft",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "subject" in data
    assert str(date.today()) in data["subject"]


async def test_get_draft_other_user_forbidden(client, db_session):
    """Fetching another user's draft → 403."""
    _, _tok, record_id = await _create_record_today(client, db_session, "draft03")
    other, other_tok = await make_user(db_session, "draft03b@t.com")
    resp = await client.get(
        f"/api/v1/daily-records/{record_id}/teams-message/draft",
        headers=auth(other_tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Send guard checks (Teams)
# ---------------------------------------------------------------------------


async def test_send_teams_requires_checked(client, db_session):
    """POST teams-message without checking first → 423."""
    _, tok, record_id = await _create_record_today(client, db_session, "tsend01")
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/teams-message",
        json={"subject": "Status", "body": "Done for today"},
        headers=auth(tok),
    )
    assert resp.status_code == 423


async def test_send_teams_idempotent(client, db_session):
    """Second POST to teams-message → 409 Conflict."""
    import uuid as _uuid

    from sqlalchemy import select as sa_select

    from app.db.models.daily_record import DailyRecord as DR

    _, tok, record_id = await _create_record_today(client, db_session, "tsend02")
    r = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert r.status_code == 200
    rid = _uuid.UUID(record_id)
    record = await db_session.scalar(sa_select(DR).where(DR.id == rid))
    assert record is not None
    record.teams_message_sent_at = datetime.now(UTC)
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/teams-message",
        json={"subject": "Status", "body": "Done for today"},
        headers=auth(tok),
    )
    assert resp.status_code == 409


async def test_send_teams_no_ms365_account(client, db_session):
    """POST teams-message without MS365 token → 422."""
    _, tok, record_id = await _create_record_today(client, db_session, "tsend03")
    r = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert r.status_code == 200
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/teams-message",
        json={"subject": "Status", "body": "Done for today"},
        headers=auth(tok),
    )
    assert resp.status_code == 422


async def test_send_teams_channel_not_configured(client, db_session):
    """POST teams-message when AdminSettings has no channel config → 503."""
    import uuid as _uuid

    from sqlalchemy import select as sa_select

    from app.db.models.user import User as U

    user, tok, record_id = await _create_record_today(client, db_session, "tsend04")
    uid = _uuid.UUID(str(user.id))
    u = await db_session.scalar(sa_select(U).where(U.id == uid))
    assert u is not None
    u.ms_graph_refresh_token = "fake-token"
    await db_session.commit()

    r = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert r.status_code == 200

    # No AdminSettings row → 503
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/teams-message",
        json={"subject": "Status", "body": "Done for today"},
        headers=auth(tok),
    )
    assert resp.status_code == 503


async def test_send_teams_happy_path(client, db_session):
    """POST teams-message with valid config → 200, teams_message_sent_at set."""
    import uuid as _uuid
    from unittest.mock import AsyncMock, patch

    from sqlalchemy import select as sa_select

    from app.db.models.admin_settings import AdminSettings
    from app.db.models.team import TeamMembership as TM
    from app.db.models.user import User as U

    user, tok, record_id = await _create_record_today(client, db_session, "tsend05")
    uid = _uuid.UUID(str(user.id))
    u = await db_session.scalar(sa_select(U).where(U.id == uid))
    assert u is not None
    u.ms_graph_refresh_token = "fake-token"
    await db_session.commit()

    membership = await db_session.scalar(
        sa_select(TM).where(TM.user_id == uid, TM.left_at.is_(None))
    )
    assert membership is not None
    cfg = AdminSettings(
        key="ms_teams_config",
        value={},
        team_id=membership.team_id,
        teams_team_id="team-abc",
        teams_channel_id="channel-xyz",
    )
    db_session.add(cfg)
    await db_session.commit()

    r = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert r.status_code == 200

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
            f"/api/v1/daily-records/{record_id}/teams-message",
            json={"subject": "Daily status", "body": "All done"},
            headers=auth(tok),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["sent_at"] is not None
    mock_post.assert_awaited_once()
    kw = mock_post.call_args.kwargs
    assert kw["teams_team_id"] == "team-abc"
    assert kw["teams_channel_id"] == "channel-xyz"


# ---------------------------------------------------------------------------
# Send guard checks (Email)
# ---------------------------------------------------------------------------


async def test_send_email_requires_checked(client, db_session):
    """POST email without checking first → 423."""
    _, tok, record_id = await _create_record_today(client, db_session, "esend01")
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/email",
        json={"subject": "Status", "body": "Done for today"},
        headers=auth(tok),
    )
    assert resp.status_code == 423


async def test_send_email_idempotent(client, db_session):
    """Second POST to email → 409 Conflict."""
    import uuid as _uuid

    from sqlalchemy import select as sa_select

    from app.db.models.daily_record import DailyRecord as DR

    _, tok, record_id = await _create_record_today(client, db_session, "esend02")
    r = await client.post(
        f"/api/v1/daily-records/{record_id}/check",
        json={"form_opened_at": datetime.now(UTC).isoformat()},
        headers=auth(tok),
    )
    assert r.status_code == 200
    rid = _uuid.UUID(record_id)
    record = await db_session.scalar(sa_select(DR).where(DR.id == rid))
    assert record is not None
    record.email_sent_at = datetime.now(UTC)
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/daily-records/{record_id}/email",
        json={"subject": "Status", "body": "Done for today"},
        headers=auth(tok),
    )
    assert resp.status_code == 409
