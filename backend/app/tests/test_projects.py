"""Tests for project endpoints (p05)."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.notification import Notification
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
    return user, create_access_token({"sub": str(user.id)})


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
    return m


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Member creates personal project → 201
# ---------------------------------------------------------------------------


async def test_member_creates_personal_project(client, db_session):
    member, tok = await make_user(db_session, "p01_member@t.com")
    team = await make_team(db_session, "p01_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.post(
        "/api/v1/projects",
        json={"name": "p01_Project", "scope": "personal"},
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "p01_Project"
    assert data["scope"] == "personal"
    assert data["created_by"] == str(member.id)


# ---------------------------------------------------------------------------
# 2. Member creates team project → 201, team_id = member's team
# ---------------------------------------------------------------------------


async def test_member_creates_team_project(client, db_session):
    member, tok = await make_user(db_session, "p02_member@t.com")
    team = await make_team(db_session, "p02_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.post(
        "/api/v1/projects",
        json={"name": "p02_Project", "scope": "team"},
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scope"] == "team"
    assert data["team_id"] == str(team.id)


# ---------------------------------------------------------------------------
# 3. Member tries cross_team → 403
# ---------------------------------------------------------------------------


async def test_member_cannot_create_cross_team_project(client, db_session):
    member, tok = await make_user(db_session, "p03_member@t.com")
    team = await make_team(db_session, "p03_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.post(
        "/api/v1/projects",
        json={"name": "p03_Project", "scope": "cross_team"},
        headers=auth(tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 4. Leader creates cross_team → 201, team_id = None
# ---------------------------------------------------------------------------


async def test_leader_creates_cross_team_project(client, db_session):
    leader, tok = await make_user(db_session, "p04_leader@t.com", is_leader=True)
    team = await make_team(db_session, "p04_Team")
    await make_membership(db_session, leader.id, team.id)

    resp = await client.post(
        "/api/v1/projects",
        json={"name": "p04_Project", "scope": "cross_team"},
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scope"] == "cross_team"
    assert data["team_id"] is None


# ---------------------------------------------------------------------------
# 5. GET projects: member sees own personal + team + all cross_team
# ---------------------------------------------------------------------------


async def test_get_projects_visibility(client, db_session):
    member, tok = await make_user(db_session, "p05_member@t.com")
    other, other_tok = await make_user(db_session, "p05_other@t.com")
    leader, leader_tok = await make_user(db_session, "p05_leader@t.com", is_leader=True)

    team = await make_team(db_session, "p05_Team")
    other_team = await make_team(db_session, "p05_OtherTeam")

    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, other.id, other_team.id)
    await make_membership(db_session, leader.id, team.id)

    # Create projects
    await client.post(
        "/api/v1/projects",
        json={"name": "p05_Personal", "scope": "personal"},
        headers=auth(tok),
    )
    await client.post(
        "/api/v1/projects",
        json={"name": "p05_Team", "scope": "team"},
        headers=auth(tok),
    )
    await client.post(
        "/api/v1/projects",
        json={"name": "p05_OtherPersonal", "scope": "personal"},
        headers=auth(other_tok),
    )
    await client.post(
        "/api/v1/projects",
        json={"name": "p05_CrossTeam", "scope": "cross_team"},
        headers=auth(leader_tok),
    )

    resp = await client.get("/api/v1/projects", headers=auth(tok))
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}

    assert "p05_Personal" in names  # own personal
    assert "p05_Team" in names  # own team
    assert "p05_CrossTeam" in names  # all cross_team
    assert "p05_OtherPersonal" not in names  # other user's personal


# ---------------------------------------------------------------------------
# 6. Soft-delete project (is_active=False) → hidden from default list
# ---------------------------------------------------------------------------


async def test_soft_delete_project(client, db_session):
    member, tok = await make_user(db_session, "p06_member@t.com")
    team = await make_team(db_session, "p06_Team")
    await make_membership(db_session, member.id, team.id)

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p06_Project", "scope": "personal"},
        headers=auth(tok),
    )
    project_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/projects/{project_id}", json={"is_active": False}, headers=auth(tok)
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False

    list_resp = await client.get("/api/v1/projects", headers=auth(tok))
    names = [p["name"] for p in list_resp.json()]
    assert "p06_Project" not in names


# ---------------------------------------------------------------------------
# 7. Promote team→cross_team by leader → scope=cross_team, notification row created
# ---------------------------------------------------------------------------


async def test_promote_project_by_leader(client, db_session):
    member, member_tok = await make_user(db_session, "p07_member@t.com")
    leader, leader_tok = await make_user(db_session, "p07_leader@t.com", is_leader=True)
    team = await make_team(db_session, "p07_Team")
    await make_membership(db_session, member.id, team.id)
    await make_membership(db_session, leader.id, team.id)

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p07_Project", "scope": "team"},
        headers=auth(member_tok),
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    promote_resp = await client.post(
        f"/api/v1/projects/{project_id}/promote", headers=auth(leader_tok)
    )
    assert promote_resp.status_code == 200
    data = promote_resp.json()
    assert data["scope"] == "cross_team"
    assert data["team_id"] is None

    # Verify notification row was created
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.trigger_type == "project_promoted",
            Notification.user_id == member.id,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None
    assert notif.data["project_id"] == project_id


# ---------------------------------------------------------------------------
# 8. Non-leader tries to promote → 403
# ---------------------------------------------------------------------------


async def test_non_leader_cannot_promote(client, db_session):
    member, tok = await make_user(db_session, "p08_member@t.com")
    team = await make_team(db_session, "p08_Team")
    await make_membership(db_session, member.id, team.id)

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p08_Project", "scope": "team"},
        headers=auth(tok),
    )
    project_id = create_resp.json()["id"]

    promote_resp = await client.post(
        f"/api/v1/projects/{project_id}/promote", headers=auth(tok)
    )
    assert promote_resp.status_code == 403


# ---------------------------------------------------------------------------
# 9. GET /projects/{project_id} — detail endpoint
# ---------------------------------------------------------------------------


async def test_owner_gets_personal_project_detail(client, db_session):
    member, tok = await make_user(db_session, "p09_member@t.com")
    team = await make_team(db_session, "p09_Team")
    await make_membership(db_session, member.id, team.id)

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p09_Personal", "scope": "personal"},
        headers=auth(tok),
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(tok))
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id
    assert resp.json()["scope"] == "personal"


async def test_member_gets_team_project_detail(client, db_session):
    member, tok = await make_user(db_session, "p10_member@t.com")
    team = await make_team(db_session, "p10_Team")
    await make_membership(db_session, member.id, team.id)

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p10_TeamProj", "scope": "team"},
        headers=auth(tok),
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(tok))
    assert resp.status_code == 200
    assert resp.json()["scope"] == "team"


async def test_any_user_gets_cross_team_project_detail(client, db_session):
    leader, leader_tok = await make_user(db_session, "p11_leader@t.com", is_leader=True)
    other, other_tok = await make_user(db_session, "p11_other@t.com")
    team = await make_team(db_session, "p11_Team")
    other_team = await make_team(db_session, "p11_OtherTeam")
    await make_membership(db_session, leader.id, team.id)
    await make_membership(db_session, other.id, other_team.id)

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p11_CrossTeam", "scope": "cross_team"},
        headers=auth(leader_tok),
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(other_tok))
    assert resp.status_code == 200
    assert resp.json()["scope"] == "cross_team"


async def test_get_project_detail_not_found(client, db_session):
    member, tok = await make_user(db_session, "p12_member@t.com")
    team = await make_team(db_session, "p12_Team")
    await make_membership(db_session, member.id, team.id)
    import uuid

    resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=auth(tok))
    assert resp.status_code == 404


async def test_non_owner_cannot_get_personal_project_detail(client, db_session):
    owner, owner_tok = await make_user(db_session, "p13_owner@t.com")
    other, other_tok = await make_user(db_session, "p13_other@t.com")
    team = await make_team(db_session, "p13_Team")
    await make_membership(db_session, owner.id, team.id)
    await make_membership(db_session, other.id, team.id)

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p13_Personal", "scope": "personal"},
        headers=auth(owner_tok),
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(other_tok))
    assert resp.status_code == 403
