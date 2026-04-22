"""Tests for controlled list endpoints: categories, self-assessment tags, blocker types."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.category import (
    BlockerType,
    Category,
    SelfAssessmentTag,
)
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
# Seed tags fixture (runs once per module)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True, scope="module")
async def seed_tags(db_session):
    tags = ["OKR", "Routine", "Team Contribution", "Company Contribution"]
    for name in tags:
        existing = await db_session.execute(
            select(SelfAssessmentTag).where(SelfAssessmentTag.name == name)
        )
        if not existing.scalar_one_or_none():
            db_session.add(SelfAssessmentTag(id=uuid4(), name=name, is_active=True))
    await db_session.commit()


# ---------------------------------------------------------------------------
# 1. Admin creates category → 201
# ---------------------------------------------------------------------------


async def test_admin_creates_category(client, db_session):
    admin, tok = await make_user(db_session, "cl01_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl01_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.post(
        "/api/v1/categories", json={"name": "cl01_Cat"}, headers=auth(tok)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "cl01_Cat"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# 2. Non-admin creates category → 403
# ---------------------------------------------------------------------------


async def test_non_admin_cannot_create_category(client, db_session):
    member, tok = await make_user(db_session, "cl02_member@t.com")
    team = await make_team(db_session, "cl02_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.post(
        "/api/v1/categories", json={"name": "cl02_Cat"}, headers=auth(tok)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. GET categories returns active only by default
# ---------------------------------------------------------------------------


async def test_get_categories_active_only(client, db_session):
    admin, tok = await make_user(db_session, "cl03_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl03_Team")
    await make_membership(db_session, admin.id, team.id)

    # Create active and inactive category
    db_session.add(
        Category(id=uuid4(), name="cl03_Active", is_active=True, sort_order=0)
    )
    db_session.add(
        Category(id=uuid4(), name="cl03_Inactive", is_active=False, sort_order=1)
    )
    await db_session.commit()

    resp = await client.get("/api/v1/categories", headers=auth(tok))
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "cl03_Active" in names
    assert "cl03_Inactive" not in names


# ---------------------------------------------------------------------------
# 4. GET categories with include_inactive=True (admin) returns all
# ---------------------------------------------------------------------------


async def test_get_categories_include_inactive_admin(client, db_session):
    admin, tok = await make_user(db_session, "cl04_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl04_Team")
    await make_membership(db_session, admin.id, team.id)

    db_session.add(
        Category(id=uuid4(), name="cl04_Active", is_active=True, sort_order=0)
    )
    db_session.add(
        Category(id=uuid4(), name="cl04_Inactive", is_active=False, sort_order=1)
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/categories?include_inactive=true", headers=auth(tok)
    )
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "cl04_Active" in names
    assert "cl04_Inactive" in names


# ---------------------------------------------------------------------------
# 5. Admin deactivates category → hidden from default list
# ---------------------------------------------------------------------------


async def test_admin_deactivates_category(client, db_session):
    admin, tok = await make_user(db_session, "cl05_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl05_Team")
    await make_membership(db_session, admin.id, team.id)

    create_resp = await client.post(
        "/api/v1/categories", json={"name": "cl05_ToDeactivate"}, headers=auth(tok)
    )
    assert create_resp.status_code == 201
    cat_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/categories/{cat_id}", json={"is_active": False}, headers=auth(tok)
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False

    list_resp = await client.get("/api/v1/categories", headers=auth(tok))
    names = [c["name"] for c in list_resp.json()]
    assert "cl05_ToDeactivate" not in names


# ---------------------------------------------------------------------------
# 6. Admin creates work type → 201
# ---------------------------------------------------------------------------


async def test_admin_creates_work_type(client, db_session):
    admin, tok = await make_user(db_session, "cl06_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl06_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.post(
        "/api/v1/work-types", json={"name": "cl06_WorkType"}, headers=auth(tok)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "cl06_WorkType"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# 7. Non-admin cannot create work type → 403
# ---------------------------------------------------------------------------


async def test_non_admin_cannot_create_work_type(client, db_session):
    member, tok = await make_user(db_session, "cl07_member@t.com")
    team = await make_team(db_session, "cl07_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.post(
        "/api/v1/work-types", json={"name": "cl07_WorkType"}, headers=auth(tok)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 8. GET self-assessment tags returns 4 seeded tags
# ---------------------------------------------------------------------------


async def test_get_self_assessment_tags(client, db_session):
    member, tok = await make_user(db_session, "cl08_member@t.com")
    team = await make_team(db_session, "cl08_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.get("/api/v1/self-assessment-tags", headers=auth(tok))
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()}
    assert {"OKR", "Routine", "Team Contribution", "Company Contribution"}.issubset(
        names
    )


# ---------------------------------------------------------------------------
# 9. Admin updates tag name → changed
# ---------------------------------------------------------------------------


async def test_admin_updates_tag_name(client, db_session):
    admin, tok = await make_user(db_session, "cl09_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl09_Team")
    await make_membership(db_session, admin.id, team.id)

    tags_resp = await client.get("/api/v1/self-assessment-tags", headers=auth(tok))
    tag = tags_resp.json()[0]
    original_name = tag["name"]

    patch_resp = await client.patch(
        f"/api/v1/self-assessment-tags/{tag['id']}",
        json={"name": "cl09_Renamed"},
        headers=auth(tok),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "cl09_Renamed"

    # Restore to avoid affecting other tests
    await client.patch(
        f"/api/v1/self-assessment-tags/{tag['id']}",
        json={"name": original_name},
        headers=auth(tok),
    )


# ---------------------------------------------------------------------------
# 10. Admin creates blocker type → 201
# ---------------------------------------------------------------------------


async def test_admin_creates_blocker_type(client, db_session):
    admin, tok = await make_user(db_session, "cl10_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl10_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.post(
        "/api/v1/blocker-types", json={"name": "cl10_Blocker"}, headers=auth(tok)
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "cl10_Blocker"
    assert resp.json()["is_active"] is True


# ---------------------------------------------------------------------------
# 11. GET blocker types returns active only
# ---------------------------------------------------------------------------


async def test_get_blocker_types_active_only(client, db_session):
    admin, tok = await make_user(db_session, "cl11_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl11_Team")
    await make_membership(db_session, admin.id, team.id)

    await client.post(
        "/api/v1/blocker-types", json={"name": "cl11_Active"}, headers=auth(tok)
    )

    # Create inactive via patch
    db_session.add(BlockerType(id=uuid4(), name="cl11_Inactive", is_active=False))
    await db_session.commit()

    resp = await client.get("/api/v1/blocker-types", headers=auth(tok))
    assert resp.status_code == 200
    names = [bt["name"] for bt in resp.json()]
    assert "cl11_Active" in names
    assert "cl11_Inactive" not in names


# ---------------------------------------------------------------------------
# 12. Admin creates self-assessment tag → 201
# ---------------------------------------------------------------------------


async def test_admin_creates_self_assessment_tag(client, db_session):
    admin, tok = await make_user(db_session, "cl12_admin@t.com", is_admin=True)
    team = await make_team(db_session, "cl12_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.post(
        "/api/v1/self-assessment-tags", json={"name": "cl12_Tag"}, headers=auth(tok)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "cl12_Tag"
    assert data["is_active"] is True
    assert "id" in data


# ---------------------------------------------------------------------------
# 13. Non-admin cannot create self-assessment tag → 403
# ---------------------------------------------------------------------------


async def test_non_admin_cannot_create_self_assessment_tag(client, db_session):
    member, tok = await make_user(db_session, "cl13_member@t.com")
    team = await make_team(db_session, "cl13_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.post(
        "/api/v1/self-assessment-tags", json={"name": "cl13_Tag"}, headers=auth(tok)
    )
    assert resp.status_code == 403
