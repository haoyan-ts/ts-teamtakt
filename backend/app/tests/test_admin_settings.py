"""Tests for admin settings endpoints: GET /admin/settings, PATCH /admin/settings."""

from datetime import UTC, datetime

from app.core.security import create_access_token
from app.db.models.admin_settings import AdminSettings
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


async def seed_settings(db, language: str = "ja"):
    from sqlalchemy import select

    result = await db.execute(
        select(AdminSettings).where(AdminSettings.key == "output_language")
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = AdminSettings(key="output_language", value=language)
        db.add(row)
    else:
        row.value = language
    await db.commit()
    await db.refresh(row)
    return row


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_admin_can_read_settings(client, db_session):
    await seed_settings(db_session, "ja")
    admin, tok = await make_user(db_session, "as01_admin@t.com", is_admin=True)
    team = await make_team(db_session, "as01_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.get("/api/v1/admin/settings", headers=auth(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert "output_language" in data
    assert data["output_language"] == "ja"


async def test_non_admin_cannot_read_settings(client, db_session):
    member, tok = await make_user(db_session, "as02_member@t.com")
    team = await make_team(db_session, "as02_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.get("/api/v1/admin/settings", headers=auth(tok))
    assert resp.status_code == 403


async def test_admin_can_update_output_language(client, db_session):
    await seed_settings(db_session, "ja")
    admin, tok = await make_user(db_session, "as03_admin@t.com", is_admin=True)
    team = await make_team(db_session, "as03_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"output_language": "en"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert resp.json()["output_language"] == "en"

    # Verify persisted
    verify = await client.get("/api/v1/admin/settings", headers=auth(tok))
    assert verify.json()["output_language"] == "en"


async def test_non_admin_cannot_update_settings(client, db_session):
    member, tok = await make_user(db_session, "as04_member@t.com")
    team = await make_team(db_session, "as04_Team")
    await make_membership(db_session, member.id, team.id)

    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"output_language": "en"},
        headers=auth(tok),
    )
    assert resp.status_code == 403


async def test_patch_invalid_language_rejected(client, db_session):
    admin, tok = await make_user(db_session, "as05_admin@t.com", is_admin=True)
    team = await make_team(db_session, "as05_Team")
    await make_membership(db_session, admin.id, team.id)

    resp = await client.patch(
        "/api/v1/admin/settings",
        json={"output_language": "xx"},
        headers=auth(tok),
    )
    assert resp.status_code == 422
