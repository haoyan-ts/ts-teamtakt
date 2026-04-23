"""Tests for project endpoints (post-#77 GitHub-linked schema)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_user(db, email, *, is_admin=False):
    user = User(
        email=email,
        display_name=email.split("@")[0],
        is_admin=is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token({"sub": str(user.id)})


async def make_active_user(db, email, *, is_admin=False):
    """Create a user and assign them to a unique team (active, non-lobby state)."""
    user, tok = await make_user(db, email, is_admin=is_admin)
    if not is_admin:
        team = await make_team(db, f"team_for_{email}")
        await make_membership(db, user.id, team.id)
    return user, tok


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


NODE_ID_A = "PVT_kwDOA1"
NODE_ID_B = "PVT_kwDOB2"
NODE_ID_C = "PVT_kwDOC3"


# ---------------------------------------------------------------------------
# 1. User creates project → 201
# ---------------------------------------------------------------------------


async def test_create_project(client, db_session):
    user, tok = await make_active_user(db_session, "p01_user@t.com")

    resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "p01_Project",
            "github_project_node_id": NODE_ID_A,
            "github_project_number": 1,
            "github_project_owner": "my-org",
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "p01_Project"
    assert data["github_project_node_id"] == NODE_ID_A
    assert data["github_project_number"] == 1
    assert data["github_project_owner"] == "my-org"
    assert data["created_by"] == str(user.id)


# ---------------------------------------------------------------------------
# 2. Duplicate node ID → 409
# ---------------------------------------------------------------------------


async def test_duplicate_node_id_returns_409(client, db_session):
    user, tok = await make_active_user(db_session, "p02_user@t.com")

    await client.post(
        "/api/v1/projects",
        json={"name": "p02_First", "github_project_node_id": NODE_ID_B},
        headers=auth(tok),
    )
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "p02_Second", "github_project_node_id": NODE_ID_B},
        headers=auth(tok),
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 3. GET /projects — creator sees own projects only
# ---------------------------------------------------------------------------


async def test_list_projects_creator_only(client, db_session):
    owner, owner_tok = await make_active_user(db_session, "p03_owner@t.com")
    other, other_tok = await make_active_user(db_session, "p03_other@t.com")

    await client.post(
        "/api/v1/projects",
        json={"name": "p03_OwnerProj", "github_project_node_id": "p03_NODE_OWNER"},
        headers=auth(owner_tok),
    )
    await client.post(
        "/api/v1/projects",
        json={"name": "p03_OtherProj", "github_project_node_id": "p03_NODE_OTHER"},
        headers=auth(other_tok),
    )

    resp = await client.get("/api/v1/projects", headers=auth(owner_tok))
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert "p03_OwnerProj" in names
    assert "p03_OtherProj" not in names


# ---------------------------------------------------------------------------
# 4. Admin sees all projects
# ---------------------------------------------------------------------------


async def test_admin_sees_all_projects(client, db_session):
    user, user_tok = await make_active_user(db_session, "p04_user@t.com")
    admin, admin_tok = await make_active_user(db_session, "p04_admin@t.com", is_admin=True)

    await client.post(
        "/api/v1/projects",
        json={"name": "p04_UserProj", "github_project_node_id": "p04_NODE_USER"},
        headers=auth(user_tok),
    )

    resp = await client.get("/api/v1/projects", headers=auth(admin_tok))
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert "p04_UserProj" in names


# ---------------------------------------------------------------------------
# 5. Soft-delete project → hidden from default list
# ---------------------------------------------------------------------------


async def test_soft_delete_project(client, db_session):
    user, tok = await make_active_user(db_session, "p05_user@t.com")

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p05_Project", "github_project_node_id": "p05_NODE"},
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
    assert "p05_Project" not in names


# ---------------------------------------------------------------------------
# 6. GET /projects/{id} — owner can access
# ---------------------------------------------------------------------------


async def test_owner_gets_project_detail(client, db_session):
    user, tok = await make_active_user(db_session, "p06_user@t.com")

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p06_Project", "github_project_node_id": "p06_NODE"},
        headers=auth(tok),
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(tok))
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id


# ---------------------------------------------------------------------------
# 7. Non-owner cannot access project detail → 403
# ---------------------------------------------------------------------------


async def test_non_owner_cannot_get_project_detail(client, db_session):
    owner, owner_tok = await make_active_user(db_session, "p07_owner@t.com")
    other, other_tok = await make_active_user(db_session, "p07_other@t.com")

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p07_Project", "github_project_node_id": "p07_NODE"},
        headers=auth(owner_tok),
    )
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth(other_tok))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 8. GET /projects/{id} — not found → 404
# ---------------------------------------------------------------------------


async def test_get_project_not_found(client, db_session):
    user, tok = await make_active_user(db_session, "p08_user@t.com")

    resp = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=auth(tok))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 9. PATCH — update github_project_number and github_project_owner
# ---------------------------------------------------------------------------


async def test_update_github_project_fields(client, db_session):
    user, tok = await make_active_user(db_session, "p09_user@t.com")

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p09_Project", "github_project_node_id": "p09_NODE"},
        headers=auth(tok),
    )
    project_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"github_project_number": 42, "github_project_owner": "new-org"},
        headers=auth(tok),
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["github_project_number"] == 42
    assert data["github_project_owner"] == "new-org"


# ---------------------------------------------------------------------------
# 10. Non-owner cannot update project → 403
# ---------------------------------------------------------------------------


async def test_non_owner_cannot_update_project(client, db_session):
    owner, owner_tok = await make_active_user(db_session, "p10_owner@t.com")
    other, other_tok = await make_active_user(db_session, "p10_other@t.com")

    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "p10_Project", "github_project_node_id": "p10_NODE"},
        headers=auth(owner_tok),
    )
    project_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Hacked"},
        headers=auth(other_tok),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 11. GET /projects/github/available — success (mocked GitHub GraphQL)
# ---------------------------------------------------------------------------


async def test_list_available_github_projects_success(client, db_session):
    user, tok = await make_active_user(db_session, "p11_user@t.com")

    # Store a plaintext token (no github_token_iv) to use the dev/local fallback path
    user.github_access_token_enc = "fake_github_token"
    await db_session.commit()

    mock_items = [
        {
            "node_id": "PVT_mock1",
            "number": 10,
            "title": "Mock Project",
            "owner_login": "mock-org",
            "url": "https://github.com/orgs/mock-org/projects/10",
        }
    ]

    with patch(
        "app.api.v1.projects.fetch_available_github_projects",
        new=AsyncMock(return_value=mock_items),
    ):
        resp = await client.get("/api/v1/projects/github/available", headers=auth(tok))

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["node_id"] == "PVT_mock1"
    assert data[0]["title"] == "Mock Project"


# ---------------------------------------------------------------------------
# 12. GET /projects/github/available — 403 when no GitHub token linked
# ---------------------------------------------------------------------------


async def test_list_available_github_projects_no_token(client, db_session):
    user, tok = await make_active_user(db_session, "p12_user@t.com")
    # user.github_access_token_enc is None by default

    resp = await client.get("/api/v1/projects/github/available", headers=auth(tok))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 13. POST /projects — old `scope` field silently ignored → 201, scope absent
# ---------------------------------------------------------------------------


async def test_create_project_scope_field_ignored(client, db_session):
    user, tok = await make_active_user(db_session, "p13_user@t.com")

    resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "p13_Project",
            "github_project_node_id": "p13_NODE",
            "scope": "team",  # legacy field — no longer in schema
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "scope" not in data


# ---------------------------------------------------------------------------
# 14. POST /projects/{id}/promote — endpoint removed → 404
# ---------------------------------------------------------------------------


async def test_promote_endpoint_removed(client, db_session):
    user, tok = await make_active_user(db_session, "p14_user@t.com")

    resp = await client.post(
        f"/api/v1/projects/{uuid.uuid4()}/promote",
        headers=auth(tok),
    )
    assert resp.status_code == 404
