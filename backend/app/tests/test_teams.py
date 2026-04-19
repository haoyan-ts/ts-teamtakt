"""Tests for team and user management endpoints (p03)."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.team import (
    Team,
    TeamMembership,
    TeamSettings,
)
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_user(db, email, *, is_leader=False, is_admin=False):
    """Create a User row and return (user, jwt_token)."""
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
    """Create a Team + default TeamSettings and return the team."""
    team = Team(name=name)
    db.add(team)
    await db.flush()
    db.add(TeamSettings(team_id=team.id))
    await db.commit()
    await db.refresh(team)
    return team


async def make_membership(db, user_id, team_id):
    """Create an active TeamMembership (left_at=NULL) and return it."""
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


# ---------------------------------------------------------------------------
# 1. Admin creates team → 201
# ---------------------------------------------------------------------------


async def test_admin_creates_team(client, db_session):
    admin, admin_tok = await make_user(db_session, "t01_admin@t.com", is_admin=True)
    home = await make_team(db_session, "t01_AdminHome")
    await make_membership(db_session, admin.id, home.id)

    resp = await client.post(
        "/api/v1/teams", json={"name": "t01_NewTeam"}, headers=auth(admin_tok)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "t01_NewTeam"
    assert "id" in data


# ---------------------------------------------------------------------------
# 2. Non-admin creates team → 403
# ---------------------------------------------------------------------------


async def test_non_admin_cannot_create_team(client, db_session):
    member, tok = await make_user(db_session, "t02_member@t.com")
    team = await make_team(db_session, "t02_SomeTeam")
    await make_membership(db_session, member.id, team.id)

    resp = await client.post(
        "/api/v1/teams", json={"name": "t02_BadTeam"}, headers=auth(tok)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. Admin deletes empty team → 200
# ---------------------------------------------------------------------------


async def test_admin_deletes_empty_team(client, db_session):
    admin, admin_tok = await make_user(db_session, "t03_admin@t.com", is_admin=True)
    home = await make_team(db_session, "t03_AdminHome")
    await make_membership(db_session, admin.id, home.id)

    empty = await make_team(db_session, "t03_EmptyTeam")

    resp = await client.delete(f"/api/v1/teams/{empty.id}", headers=auth(admin_tok))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Admin tries to delete team with active members → 409
# ---------------------------------------------------------------------------


async def test_admin_cannot_delete_team_with_members(client, db_session):
    admin, admin_tok = await make_user(db_session, "t04_admin@t.com", is_admin=True)
    home = await make_team(db_session, "t04_AdminHome")
    await make_membership(db_session, admin.id, home.id)

    target = await make_team(db_session, "t04_TeamWithMembers")
    member, _ = await make_user(db_session, "t04_member@t.com")
    await make_membership(db_session, member.id, target.id)

    resp = await client.delete(f"/api/v1/teams/{target.id}", headers=auth(admin_tok))
    assert resp.status_code == 409
    assert "Remove or reassign" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Lobby user creates join request → 201
# ---------------------------------------------------------------------------


async def test_lobby_user_creates_join_request(client, db_session):
    lobby, tok = await make_user(db_session, "t05_lobby@t.com")  # no membership = lobby
    team = await make_team(db_session, "t05_JoinTeam")

    resp = await client.post(
        f"/api/v1/teams/{team.id}/join-requests", headers=auth(tok)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["team_id"] == str(team.id)


# ---------------------------------------------------------------------------
# 6. Leader approves join request → user gets active membership, exits lobby
# ---------------------------------------------------------------------------


async def test_leader_approves_join_request(client, db_session):
    leader, leader_tok = await make_user(db_session, "t06_leader@t.com", is_leader=True)
    team = await make_team(db_session, "t06_LeaderTeam")
    await make_membership(db_session, leader.id, team.id)

    applicant, app_tok = await make_user(db_session, "t06_applicant@t.com")

    # Create join request (lobby user)
    r1 = await client.post(
        f"/api/v1/teams/{team.id}/join-requests", headers=auth(app_tok)
    )
    assert r1.status_code == 201
    req_id = r1.json()["id"]

    # Leader approves
    r2 = await client.patch(
        f"/api/v1/teams/{team.id}/join-requests/{req_id}",
        json={"action": "approve"},
        headers=auth(leader_tok),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"

    # Applicant should now have an active membership
    result = await db_session.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == applicant.id,
            TeamMembership.left_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 7. Leader rejects join request → status=rejected
# ---------------------------------------------------------------------------


async def test_leader_rejects_join_request(client, db_session):
    leader, leader_tok = await make_user(db_session, "t07_leader@t.com", is_leader=True)
    team = await make_team(db_session, "t07_LeaderTeam")
    await make_membership(db_session, leader.id, team.id)

    applicant, app_tok = await make_user(db_session, "t07_applicant@t.com")

    r1 = await client.post(
        f"/api/v1/teams/{team.id}/join-requests", headers=auth(app_tok)
    )
    req_id = r1.json()["id"]

    r2 = await client.patch(
        f"/api/v1/teams/{team.id}/join-requests/{req_id}",
        json={"action": "reject"},
        headers=auth(leader_tok),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# 8. Role assignment: admin sets is_leader=True → user now has is_leader
# ---------------------------------------------------------------------------


async def test_admin_sets_leader_role(client, db_session):
    admin, admin_tok = await make_user(db_session, "t08_admin@t.com", is_admin=True)
    home = await make_team(db_session, "t08_AdminHome")
    await make_membership(db_session, admin.id, home.id)

    target, _ = await make_user(db_session, "t08_target@t.com")

    resp = await client.patch(
        f"/api/v1/users/{target.id}/roles",
        json={"is_leader": True},
        headers=auth(admin_tok),
    )
    assert resp.status_code == 200
    assert resp.json()["is_leader"] is True


# ---------------------------------------------------------------------------
# 9. Non-admin tries to set roles → 403
# ---------------------------------------------------------------------------


async def test_non_admin_cannot_set_roles(client, db_session):
    member, tok = await make_user(db_session, "t09_member@t.com")
    team = await make_team(db_session, "t09_SomeTeam")
    await make_membership(db_session, member.id, team.id)

    target, _ = await make_user(db_session, "t09_target@t.com")

    resp = await client.patch(
        f"/api/v1/users/{target.id}/roles",
        json={"is_leader": True},
        headers=auth(tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 10. Team transfer: user in team A approved to team B
#     → team A membership closed (left_at set), team B membership created
# ---------------------------------------------------------------------------


async def test_team_transfer_on_approve(client, db_session):
    leader, leader_tok = await make_user(db_session, "t10_leader@t.com", is_leader=True)
    team_b = await make_team(db_session, "t10_TeamB")
    await make_membership(db_session, leader.id, team_b.id)

    user, user_tok = await make_user(db_session, "t10_user@t.com")
    team_a = await make_team(db_session, "t10_TeamA")
    membership_a = await make_membership(db_session, user.id, team_a.id)

    # User requests to join team B
    r1 = await client.post(
        f"/api/v1/teams/{team_b.id}/join-requests", headers=auth(user_tok)
    )
    assert r1.status_code == 201
    req_id = r1.json()["id"]

    # Leader approves
    r2 = await client.patch(
        f"/api/v1/teams/{team_b.id}/join-requests/{req_id}",
        json={"action": "approve"},
        headers=auth(leader_tok),
    )
    assert r2.status_code == 200

    # Team A membership must be closed
    await db_session.refresh(membership_a)
    assert membership_a.left_at is not None

    # Team B membership must exist and be active
    result = await db_session.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == user.id,
            TeamMembership.team_id == team_b.id,
            TeamMembership.left_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 11. Admin directly assigns user to team → 201, membership created
# ---------------------------------------------------------------------------


async def test_admin_direct_assign(client, db_session):
    admin, admin_tok = await make_user(db_session, "t11_admin@t.com", is_admin=True)
    home = await make_team(db_session, "t11_AdminHome")
    await make_membership(db_session, admin.id, home.id)

    user, _ = await make_user(db_session, "t11_assignee@t.com")
    target = await make_team(db_session, "t11_TargetTeam")

    resp = await client.post(
        f"/api/v1/teams/{target.id}/members",
        json={"user_id": str(user.id)},
        headers=auth(admin_tok),
    )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == user.id,
            TeamMembership.team_id == target.id,
            TeamMembership.left_at.is_(None),
        )
    )
    assert result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 12. GET /users/me works for lobby user
# ---------------------------------------------------------------------------


async def test_users_me_lobby(client, db_session):
    lobby, tok = await make_user(db_session, "t12_lobby@t.com")

    resp = await client.get("/api/v1/users/me", headers=auth(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "t12_lobby@t.com"
    assert data["lobby"] is True
    assert data["team"] is None


# ---------------------------------------------------------------------------
# 13. GET /users lists all users (admin only)
# ---------------------------------------------------------------------------


async def test_admin_list_users(client, db_session):
    admin, admin_tok = await make_user(db_session, "t13_admin@t.com", is_admin=True)
    home = await make_team(db_session, "t13_AdminHome")
    await make_membership(db_session, admin.id, home.id)

    resp = await client.get("/api/v1/users", headers=auth(admin_tok))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    emails = [u["email"] for u in resp.json()]
    assert "t13_admin@t.com" in emails


# ---------------------------------------------------------------------------
# 14. GET /teams/{team_id} — detail endpoint
# ---------------------------------------------------------------------------


async def test_member_gets_team_detail(client, db_session):
    member, tok = await make_user(db_session, "t14_member@t.com")
    team = await make_team(db_session, "t14_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.get(f"/api/v1/teams/{team.id}", headers=auth(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(team.id)
    assert data["name"] == "t14_Team"


async def test_get_team_detail_not_found(client, db_session):
    admin, tok = await make_user(db_session, "t14b_admin@t.com", is_admin=True)
    import uuid

    resp = await client.get(f"/api/v1/teams/{uuid.uuid4()}", headers=auth(tok))
    assert resp.status_code == 404


async def test_non_member_cannot_get_team_detail(client, db_session):
    outsider, tok = await make_user(db_session, "t14c_outsider@t.com")
    team = await make_team(db_session, "t14c_Team")
    # outsider is NOT a member of this team

    resp = await client.get(f"/api/v1/teams/{team.id}", headers=auth(tok))
    assert resp.status_code == 403
