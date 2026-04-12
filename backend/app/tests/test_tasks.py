"""Tests for Task CRUD (p11) endpoints."""

from datetime import UTC, datetime

from app.core.security import create_access_token
from app.db.models.category import Category
from app.db.models.project import Project, ProjectScope
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_user(db, email, *, is_leader=False):
    user = User(
        email=email,
        display_name=email.split("@")[0],
        is_leader=is_leader,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return user, token


async def make_team_with_member(db, user_id, name="Team"):
    team = Team(name=name)
    db.add(team)
    await db.flush()
    db.add(TeamSettings(team_id=team.id))
    m = TeamMembership(user_id=user_id, team_id=team.id, joined_at=datetime.now(UTC))
    db.add(m)
    await db.commit()
    await db.refresh(team)
    return team


async def make_category(db, name="Cat"):
    cat = Category(name=name, is_active=True, sort_order=1)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def make_project(db, created_by):
    p = Project(name="Proj", scope=ProjectScope.personal, created_by=created_by)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def task_payload(category_id, project_id, **overrides):
    base = {
        "title": "My task",
        "category_id": str(category_id),
        "project_id": str(project_id),
        "estimated_effort": 3,
        "status": "todo",
    }
    base.update(overrides)
    return base


# ===========================================================================
# Create
# ===========================================================================


async def test_create_task_ok(client, db_session):
    user, tok = await make_user(db_session, "tsk01@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "tsk01_Cat")
    proj = await make_project(db_session, user.id)

    resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id),
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My task"
    assert data["status"] == "todo"
    assert data["is_active"] is True
    assert data["closed_at"] is None


async def test_create_task_done_sets_closed_at(client, db_session):
    user, tok = await make_user(db_session, "tsk02@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "tsk02_Cat")
    proj = await make_project(db_session, user.id)

    resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id, status="done"),
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["closed_at"] is not None


# ===========================================================================
# Read
# ===========================================================================


async def test_get_task_by_id(client, db_session):
    user, tok = await make_user(db_session, "tsk03@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "tsk03_Cat")
    proj = await make_project(db_session, user.id)

    create_resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id, title="Read me"),
        headers=auth(tok),
    )
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/tasks/{task_id}", headers=auth(tok))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Read me"


# ===========================================================================
# Update — github_issue_url immutability
# ===========================================================================


async def test_task_github_url_immutable(client, db_session):
    user, tok = await make_user(db_session, "tsk04@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "tsk04_Cat")
    proj = await make_project(db_session, user.id)

    create_resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(
            cat.id, proj.id, github_issue_url="https://github.com/org/repo/issues/1"
        ),
        headers=auth(tok),
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    # Attempt to change github_issue_url → must be rejected
    resp = await client.put(
        f"/api/v1/tasks/{task_id}",
        json={"github_issue_url": "https://github.com/org/repo/issues/99"},
        headers=auth(tok),
    )
    assert resp.status_code == 422


async def test_task_update_status_ok(client, db_session):
    user, tok = await make_user(db_session, "tsk05@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "tsk05_Cat")
    proj = await make_project(db_session, user.id)

    create_resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id),
        headers=auth(tok),
    )
    task_id = create_resp.json()["id"]

    # Transition to done → closed_at should be set
    resp = await client.put(
        f"/api/v1/tasks/{task_id}",
        json={"status": "done"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert resp.json()["closed_at"] is not None


# ===========================================================================
# Soft-delete
# ===========================================================================


async def test_task_soft_delete(client, db_session):
    user, tok = await make_user(db_session, "tsk06@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "tsk06_Cat")
    proj = await make_project(db_session, user.id)

    create_resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id),
        headers=auth(tok),
    )
    task_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/tasks/{task_id}", headers=auth(tok))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/tasks/{task_id}", headers=auth(tok))
    # Record should either be hidden (404) or marked inactive
    if get_resp.status_code == 200:
        assert get_resp.json()["is_active"] is False
    else:
        assert get_resp.status_code == 404


# ===========================================================================
# Unique github_issue_url per user
# ===========================================================================


async def test_unique_github_issue_url_per_user(client, db_session):
    user, tok = await make_user(db_session, "tsk07@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "tsk07_Cat")
    proj = await make_project(db_session, user.id)
    issue_url = "https://github.com/org/repo/issues/42"

    first = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id, github_issue_url=issue_url),
        headers=auth(tok),
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id, github_issue_url=issue_url),
        headers=auth(tok),
    )
    assert second.status_code == 409


# ===========================================================================
# Auto-fill stub → 501
# ===========================================================================


async def test_task_autofill_returns_501(client, db_session):
    user, tok = await make_user(db_session, "tsk08@t.com")
    await make_team_with_member(db_session, user.id)

    resp = await client.post(
        "/api/v1/tasks/autofill",
        json={"github_issue_url": "https://github.com/org/repo/issues/1"},
        headers=auth(tok),
    )
    assert resp.status_code == 501
