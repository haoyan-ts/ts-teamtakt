"""Tests for Export (p14) and SharingGrant (p14) endpoints."""

from datetime import UTC, datetime

from app.core.security import create_access_token
from app.db.models.category import Category
from app.db.models.daily_record import DailyRecord
from app.db.models.project import Project
from app.db.models.task import DailyWorkLog, Task, TaskStatus
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers (mirror pattern from test_teams.py)
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
    from datetime import datetime

    m = TeamMembership(
        user_id=user_id,
        team_id=team_id,
        joined_at=datetime.now(UTC),
    )
    db.add(m)
    await db.commit()
    return m


async def make_category(db, name="TestCat"):
    cat = Category(name=name, is_active=True, sort_order=1)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def make_project(
    db, name, created_by
):
    p = Project(
        name=name,
        github_project_node_id=f"PVT_{name}",
        created_by=created_by,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def make_daily_record(db, user_id, record_date_str):
    from datetime import date

    dr = DailyRecord(
        user_id=user_id,
        record_date=date.fromisoformat(record_date_str),
        day_load=3,
        day_insight="test note",
        form_opened_at=datetime.now(UTC),
    )
    db.add(dr)
    await db.commit()
    await db.refresh(dr)
    return dr


async def make_work_log(
    db, daily_record_id, category_id, project_id, user_id, sort_order=1
):
    task = Task(
        title="Do something",
        assignee_id=user_id,
        created_by=user_id,
        project_id=project_id,
        category_id=category_id,
        status=TaskStatus.running,
    )
    db.add(task)
    await db.flush()
    log = DailyWorkLog(
        task_id=task.id,
        daily_record_id=daily_record_id,
        effort=2,
        sort_order=sort_order,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Export: my-records
# ===========================================================================


async def test_export_my_records_csv(client, db_session):
    user, tok = await make_user(db_session, "exp01_user@t.com")
    cat = await make_category(db_session, "exp01_Cat")
    proj = await make_project(db_session, "exp01_Proj", user.id)
    dr = await make_daily_record(db_session, user.id, "2025-01-06")
    await make_work_log(db_session, dr.id, cat.id, proj.id, user.id)

    resp = await client.get(
        "/api/v1/export/my-records?format=csv",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.content.decode("utf-8-sig")
    assert "2025-01-06" in body
    assert "Do something" in body


async def test_export_my_records_xlsx(client, db_session):
    user, tok = await make_user(db_session, "exp02_user@t.com")
    cat = await make_category(db_session, "exp02_Cat")
    proj = await make_project(db_session, "exp02_Proj", user.id)
    dr = await make_daily_record(db_session, user.id, "2025-01-07")
    await make_work_log(db_session, dr.id, cat.id, proj.id, user.id)

    resp = await client.get(
        "/api/v1/export/my-records?format=xlsx",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    ct = resp.headers["content-type"]
    assert "spreadsheetml" in ct or "openxmlformats" in ct


# ===========================================================================
# Export: team records (leader)
# ===========================================================================


async def test_leader_export_team_csv(client, db_session):
    leader, l_tok = await make_user(db_session, "exp03_leader@t.com", is_leader=True)
    member, _ = await make_user(db_session, "exp03_member@t.com")
    team = await make_team(db_session, "exp03_Team")
    await make_membership(db_session, leader.id, team.id)
    await make_membership(db_session, member.id, team.id)
    cat = await make_category(db_session, "exp03_Cat")
    proj = await make_project(db_session, "exp03_Proj", member.id)
    dr = await make_daily_record(db_session, member.id, "2025-01-08")
    await make_work_log(db_session, dr.id, cat.id, proj.id, member.id)

    resp = await client.get(
        f"/api/v1/export/team/{team.id}?format=csv",
        headers=auth(l_tok),
    )
    assert resp.status_code == 200
    body = resp.content.decode("utf-8-sig")
    assert "2025-01-08" in body


async def test_non_leader_cannot_export_team(client, db_session):
    user, tok = await make_user(db_session, "exp04_user@t.com")
    team = await make_team(db_session, "exp04_Team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.get(
        f"/api/v1/export/team/{team.id}",
        headers=auth(tok),
    )
    assert resp.status_code == 403


# ===========================================================================
# Export: bulk (admin)
# ===========================================================================


async def test_admin_bulk_export_xlsx(client, db_session):
    admin, a_tok = await make_user(db_session, "exp05_admin@t.com", is_admin=True)

    resp = await client.get(
        "/api/v1/export/bulk?format=xlsx",
        headers=auth(a_tok),
    )
    assert resp.status_code == 200
    ct = resp.headers["content-type"]
    assert "spreadsheetml" in ct or "openxmlformats" in ct


async def test_non_admin_cannot_bulk_export(client, db_session):
    user, tok = await make_user(db_session, "exp06_user@t.com")

    resp = await client.get("/api/v1/export/bulk", headers=auth(tok))
    assert resp.status_code == 403


# ===========================================================================
# SharingGrant: create + list + revoke
# ===========================================================================


async def test_create_sharing_grant(client, db_session):
    leaderA, tokA = await make_user(db_session, "sg01_leaderA@t.com", is_leader=True)
    leaderB, tokB = await make_user(db_session, "sg01_leaderB@t.com", is_leader=True)
    team = await make_team(db_session, "sg01_Team")
    await make_membership(db_session, leaderA.id, team.id)

    resp = await client.post(
        "/api/v1/sharing-grants",
        json={"granted_to_leader_id": str(leaderB.id)},
        headers=auth(tokA),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["granted_to_leader_id"] == str(leaderB.id)
    assert data["team_id"] == str(team.id)
    assert data["revoked_at"] is None


async def test_duplicate_sharing_grant_409(client, db_session):
    leaderA, tokA = await make_user(db_session, "sg02_leaderA@t.com", is_leader=True)
    leaderB, _ = await make_user(db_session, "sg02_leaderB@t.com", is_leader=True)
    team = await make_team(db_session, "sg02_Team")
    await make_membership(db_session, leaderA.id, team.id)

    payload = {"granted_to_leader_id": str(leaderB.id)}
    r1 = await client.post("/api/v1/sharing-grants", json=payload, headers=auth(tokA))
    assert r1.status_code == 201

    r2 = await client.post("/api/v1/sharing-grants", json=payload, headers=auth(tokA))
    assert r2.status_code == 409


async def test_list_sharing_grants(client, db_session):
    leaderA, tokA = await make_user(db_session, "sg03_leaderA@t.com", is_leader=True)
    leaderB, tokB = await make_user(db_session, "sg03_leaderB@t.com", is_leader=True)
    team = await make_team(db_session, "sg03_Team")
    await make_membership(db_session, leaderA.id, team.id)

    await client.post(
        "/api/v1/sharing-grants",
        json={"granted_to_leader_id": str(leaderB.id)},
        headers=auth(tokA),
    )

    # granter sees it
    rA = await client.get("/api/v1/sharing-grants", headers=auth(tokA))
    assert rA.status_code == 200
    grants_A = [g for g in rA.json() if g["team_id"] == str(team.id)]
    assert len(grants_A) >= 1

    # grantee sees it
    rB = await client.get("/api/v1/sharing-grants", headers=auth(tokB))
    assert rB.status_code == 200
    grants_B = [g for g in rB.json() if g["team_id"] == str(team.id)]
    assert len(grants_B) >= 1


async def test_revoke_sharing_grant(client, db_session):
    leaderA, tokA = await make_user(db_session, "sg04_leaderA@t.com", is_leader=True)
    leaderB, _ = await make_user(db_session, "sg04_leaderB@t.com", is_leader=True)
    team = await make_team(db_session, "sg04_Team")
    await make_membership(db_session, leaderA.id, team.id)

    r = await client.post(
        "/api/v1/sharing-grants",
        json={"granted_to_leader_id": str(leaderB.id)},
        headers=auth(tokA),
    )
    grant_id = r.json()["id"]

    # Revoke
    rd = await client.delete(f"/api/v1/sharing-grants/{grant_id}", headers=auth(tokA))
    assert rd.status_code == 204

    # Now list should show 0 active for this team
    rlist = await client.get("/api/v1/sharing-grants", headers=auth(tokA))
    active = [
        g for g in rlist.json() if g["id"] == grant_id and g["revoked_at"] is None
    ]
    assert len(active) == 0


async def test_revoke_already_revoked_409(client, db_session):
    leaderA, tokA = await make_user(db_session, "sg05_leaderA@t.com", is_leader=True)
    leaderB, _ = await make_user(db_session, "sg05_leaderB@t.com", is_leader=True)
    team = await make_team(db_session, "sg05_Team")
    await make_membership(db_session, leaderA.id, team.id)

    r = await client.post(
        "/api/v1/sharing-grants",
        json={"granted_to_leader_id": str(leaderB.id)},
        headers=auth(tokA),
    )
    grant_id = r.json()["id"]
    await client.delete(f"/api/v1/sharing-grants/{grant_id}", headers=auth(tokA))
    r2 = await client.delete(f"/api/v1/sharing-grants/{grant_id}", headers=auth(tokA))
    assert r2.status_code == 409


async def test_non_transitivity_enforced(client, db_session):
    """
    LeaderA grants to LeaderB. LeaderB may NOT create a grant for the same data.
    B is not a direct team leader for A's team, so creating a grant for A's team_id
    would fail because B is not in that team.
    """
    leaderA, tokA = await make_user(db_session, "sg06_leaderA@t.com", is_leader=True)
    leaderB, tokB = await make_user(db_session, "sg06_leaderB@t.com", is_leader=True)
    leaderC, _ = await make_user(db_session, "sg06_leaderC@t.com", is_leader=True)
    teamA = await make_team(db_session, "sg06_TeamA")
    teamB = await make_team(db_session, "sg06_TeamB")
    await make_membership(db_session, leaderA.id, teamA.id)
    await make_membership(db_session, leaderB.id, teamB.id)

    # A grants B
    await client.post(
        "/api/v1/sharing-grants",
        json={"granted_to_leader_id": str(leaderB.id)},
        headers=auth(tokA),
    )

    # B tries to grant C access — B can only grant for B's own team (teamB), not teamA
    # So B creating a grant for C is allowed only for teamB data.
    # The non-transitivity invariant is that B cannot re-share A's data.
    # When B posts /sharing-grants, the endpoint uses B's own team (teamB), NOT teamA.
    r = await client.post(
        "/api/v1/sharing-grants",
        json={"granted_to_leader_id": str(leaderC.id)},
        headers=auth(tokB),
    )
    # B can grant C access to B's own team (teamB) — this is allowed
    assert r.status_code == 201
    assert r.json()["team_id"] == str(teamB.id)  # NOT teamA
