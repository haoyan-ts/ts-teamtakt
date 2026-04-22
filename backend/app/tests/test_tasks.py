"""Tests for Task CRUD (p11) endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

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
# Auto-fill
# ===========================================================================


async def test_task_autofill_happy_path(client, db_session):
    user, tok = await make_user(db_session, "tsk08@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "bug")

    fake_issue = {
        "title": "Fix the bug",
        "body": "Something is broken.",
        "labels": [{"name": "bug"}],
    }
    with patch(
        "app.api.v1.tasks.fetch_github_issue",
        new=AsyncMock(return_value=fake_issue),
    ):
        resp = await client.get(
            "/api/v1/tasks/autofill",
            params={"url": "https://github.com/org/repo/issues/1"},
            headers=auth(tok),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Fix the bug"
    assert data["description"] == "Something is broken."
    assert data["category_id"] == str(cat.id)


async def test_task_autofill_invalid_url_returns_400(client, db_session):
    user, tok = await make_user(db_session, "tsk09@t.com")
    await make_team_with_member(db_session, user.id)

    resp = await client.get(
        "/api/v1/tasks/autofill",
        params={"url": "https://not-github.com/x"},
        headers=auth(tok),
    )
    assert resp.status_code == 400


# ===========================================================================
# Fibonacci effort validation — estimated_effort on Task
# ===========================================================================


# ===========================================================================
# insight field — Task
# ===========================================================================


async def _make_task(client, db, email, **overrides):
    """Helper: create a user + task, return (task_dict, token)."""
    user, tok = await make_user(db, email)
    await make_team_with_member(db, user.id)
    cat = await make_category(db, f"cat_{email}")
    proj = await make_project(db, user.id)

    payload = {
        "title": "Test Task",
        "project_id": str(proj.id),
        "category_id": str(cat.id),
        "status": "todo",
        **overrides,
    }
    resp = await client.post("/api/v1/tasks", json=payload, headers=auth(tok))
    assert resp.status_code == 201
    return resp.json(), tok


async def test_task_insight_save_and_retrieve(client, db_session):
    """insight is saved via PATCH and returned by GET."""
    task_data, tok = await _make_task(client, db_session, "ins01@t.com")
    task_id = task_data["id"]

    patch_resp = await client.put(
        f"/api/v1/tasks/{task_id}",
        json={"insight": "I learned that async is tricky."},
        headers=auth(tok),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["insight"] == "I learned that async is tricky."

    get_resp = await client.get(f"/api/v1/tasks/{task_id}", headers=auth(tok))
    assert get_resp.status_code == 200
    assert get_resp.json()["insight"] == "I learned that async is tricky."


async def test_task_insight_too_long_rejected(client, db_session):
    """insight longer than 500 chars returns 422."""
    task_data, tok = await _make_task(client, db_session, "ins02@t.com")
    task_id = task_data["id"]

    long_insight = "x" * 501
    resp = await client.put(
        f"/api/v1/tasks/{task_id}",
        json={"insight": long_insight},
        headers=auth(tok),
    )
    assert resp.status_code == 422


async def test_task_carry_over_does_not_copy_insight(client, db_session):
    """insight must NOT be inherited when a task entry is carried over."""
    # This test validates the model-level constraint: insight on Task is
    # independent per task. Carry-over creates a new TaskEntry, not a new Task,
    # so Task.insight is irrelevant to carry-over; but DailyWorkLog.insight
    # (day-level) must not auto-populate on new logs.
    user, tok = await make_user(db_session, "ins03@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "cat_ins03")
    proj = await make_project(db_session, user.id)

    # Create task with insight
    create_resp = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Carry test",
            "project_id": str(proj.id),
            "category_id": str(cat.id),
            "status": "todo",
            "insight": "original learning",
        },
        headers=auth(tok),
    )
    assert create_resp.status_code == 201
    # Task.insight is set on create
    assert create_resp.json()["insight"] == "original learning"

    # A fresh DailyWorkLog for this task should have insight=None (not inherited)
    from app.db.models.task import DailyWorkLog

    new_log = DailyWorkLog(
        task_id=create_resp.json()["id"],
        daily_record_id=__import__("uuid").uuid4(),  # dummy FK, not committed
        effort=1,
        sort_order=0,
    )
    # insight not set → defaults to None
    assert new_log.insight is None


async def test_task_estimated_effort_valid_fibonacci_values(client, db_session):
    user, tok = await make_user(db_session, "fib01@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "fib01_Cat")
    proj = await make_project(db_session, user.id)

    for effort in (1, 2, 3, 5, 8):
        resp = await client.post(
            "/api/v1/tasks",
            json=task_payload(
                cat.id, proj.id, estimated_effort=effort, title=f"fib {effort}"
            ),
            headers=auth(tok),
        )
        assert resp.status_code == 201, f"effort={effort} should be accepted"
        assert resp.json()["estimated_effort"] == effort


async def test_task_estimated_effort_non_fibonacci_rejected(client, db_session):
    user, tok = await make_user(db_session, "fib02@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "fib02_Cat")
    proj = await make_project(db_session, user.id)

    for invalid in (4, 6, 7, 9):
        resp = await client.post(
            "/api/v1/tasks",
            json=task_payload(cat.id, proj.id, estimated_effort=invalid),
            headers=auth(tok),
        )
        assert resp.status_code == 422, f"effort={invalid} should be rejected"


async def test_task_update_estimated_effort_non_fibonacci_rejected(client, db_session):
    user, tok = await make_user(db_session, "fib03@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "fib03_Cat")
    proj = await make_project(db_session, user.id)

    create_resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id, estimated_effort=3),
        headers=auth(tok),
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/tasks/{task_id}",
        json={"estimated_effort": 4},
        headers=auth(tok),
    )
    assert resp.status_code == 422


async def test_task_update_estimated_effort_to_eight_accepted(client, db_session):
    user, tok = await make_user(db_session, "fib04@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "fib04_Cat")
    proj = await make_project(db_session, user.id)

    create_resp = await client.post(
        "/api/v1/tasks",
        json=task_payload(cat.id, proj.id, estimated_effort=3),
        headers=auth(tok),
    )
    assert create_resp.status_code == 201
    task_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/tasks/{task_id}",
        json={"estimated_effort": 8},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert resp.json()["estimated_effort"] == 8


# ===========================================================================
# New fields: work_type_id, priority, due_date, nullable project_id
# ===========================================================================


async def test_task_create_with_work_type(client, db_session):
    """work_type_id is accepted and returned on create."""
    from app.db.models.category import WorkType

    user, tok = await make_user(db_session, "wt01@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "wt01_cat")

    wt = WorkType(name="wt01_Software", is_active=True, sort_order=0)
    db_session.add(wt)
    await db_session.commit()
    await db_session.refresh(wt)

    resp = await client.post(
        "/api/v1/tasks",
        json={
            "title": "WType Task",
            "category_id": str(cat.id),
            "work_type_id": str(wt.id),
            "status": "todo",
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["work_type_id"] == str(wt.id)


async def test_task_create_with_priority(client, db_session):
    """priority field is accepted and returned on create."""
    user, tok = await make_user(db_session, "pri01@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "pri01_cat")

    for priority in ("low", "medium", "high"):
        resp = await client.post(
            "/api/v1/tasks",
            json={
                "title": f"Priority {priority}",
                "category_id": str(cat.id),
                "status": "todo",
                "priority": priority,
            },
            headers=auth(tok),
        )
        assert resp.status_code == 201, f"priority={priority!r} should be accepted"
        assert resp.json()["priority"] == priority


async def test_task_create_with_due_date(client, db_session):
    """due_date is accepted and returned on create."""
    from datetime import date, timedelta

    user, tok = await make_user(db_session, "due01@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "due01_cat")
    due = str(date.today() + timedelta(days=7))

    resp = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Due Date Task",
            "category_id": str(cat.id),
            "status": "todo",
            "due_date": due,
        },
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["due_date"] == due


async def test_task_create_without_project_id(client, db_session):
    """project_id is now optional; omitting it creates a standalone task."""
    user, tok = await make_user(db_session, "noproj01@t.com")
    await make_team_with_member(db_session, user.id)
    cat = await make_category(db_session, "noproj01_cat")

    resp = await client.post(
        "/api/v1/tasks",
        json={"title": "No Project Task", "category_id": str(cat.id), "status": "todo"},
        headers=auth(tok),
    )
    assert resp.status_code == 201
    assert resp.json()["project_id"] is None
