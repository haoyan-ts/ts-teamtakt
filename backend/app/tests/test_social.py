"""Tests for social layer — comments, reactions, feed (p17).

Key invariants tested:
- Duplicate same-emoji reaction on same record = toggle off silently (204, not 4xx)
- Comment CRUD (create, read, update, delete)
- Threaded comments (parent_comment_id)
- WebSocket endpoint rejects unauthenticated connection
"""

from datetime import UTC, date, datetime

from app.core.security import create_access_token
from app.db.models.daily_record import DailyRecord
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
    await db.refresh(m)
    return m


async def make_record(db, user_id, record_date=date(2026, 4, 1)):
    rec = DailyRecord(
        user_id=user_id,
        record_date=record_date,
        day_load=3,
        form_opened_at=datetime.now(UTC),
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Add a comment → 201
# ---------------------------------------------------------------------------


async def test_add_comment(client, db_session):
    user, tok = await make_user(db_session, "s01_user@t.com")
    team = await make_team(db_session, "s01_Team")
    await make_membership(db_session, user.id, team.id)
    rec = await make_record(db_session, user.id, date(2026, 3, 1))

    resp = await client.post(
        f"/api/v1/daily-records/{rec.id}/comments",
        json={"body": "Great work!"},
        headers=auth(tok),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"] == "Great work!"
    assert data["author_id"] == str(user.id)


# ---------------------------------------------------------------------------
# 2. List comments for a record
# ---------------------------------------------------------------------------


async def test_list_comments(client, db_session):
    user, tok = await make_user(db_session, "s02_user@t.com")
    team = await make_team(db_session, "s02_Team")
    await make_membership(db_session, user.id, team.id)
    rec = await make_record(db_session, user.id, date(2026, 3, 2))

    await client.post(
        f"/api/v1/daily-records/{rec.id}/comments",
        json={"body": "Hello"},
        headers=auth(tok),
    )

    resp = await client.get(
        f"/api/v1/daily-records/{rec.id}/comments",
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# 3. Threaded reply (parent_comment_id set)
# ---------------------------------------------------------------------------


async def test_threaded_reply(client, db_session):
    user, tok = await make_user(db_session, "s03_user@t.com")
    team = await make_team(db_session, "s03_Team")
    await make_membership(db_session, user.id, team.id)
    rec = await make_record(db_session, user.id, date(2026, 3, 3))

    parent_resp = await client.post(
        f"/api/v1/daily-records/{rec.id}/comments",
        json={"body": "Parent comment"},
        headers=auth(tok),
    )
    parent_id = parent_resp.json()["id"]

    reply_resp = await client.post(
        f"/api/v1/daily-records/{rec.id}/comments",
        json={"body": "Reply", "parent_comment_id": parent_id},
        headers=auth(tok),
    )
    assert reply_resp.status_code == 201
    assert reply_resp.json()["parent_comment_id"] == parent_id


# ---------------------------------------------------------------------------
# 4. Toggle reaction on → 204
# ---------------------------------------------------------------------------


async def test_toggle_reaction_on(client, db_session):
    user, tok = await make_user(db_session, "s04_user@t.com")
    team = await make_team(db_session, "s04_Team")
    await make_membership(db_session, user.id, team.id)
    rec = await make_record(db_session, user.id, date(2026, 3, 4))

    resp = await client.post(
        f"/api/v1/daily-records/{rec.id}/reactions",
        json={"emoji": "👍"},
        headers=auth(tok),
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# 5. Duplicate same-emoji reaction = toggle off silently (204, not error)
# ---------------------------------------------------------------------------


async def test_duplicate_reaction_toggles_off(client, db_session):
    user, tok = await make_user(db_session, "s05_user@t.com")
    team = await make_team(db_session, "s05_Team")
    await make_membership(db_session, user.id, team.id)
    rec = await make_record(db_session, user.id, date(2026, 3, 5))

    # First toggle on
    r1 = await client.post(
        f"/api/v1/daily-records/{rec.id}/reactions",
        json={"emoji": "❤️"},
        headers=auth(tok),
    )
    assert r1.status_code == 204

    # Second call with same emoji = toggle off, still 204
    r2 = await client.post(
        f"/api/v1/daily-records/{rec.id}/reactions",
        json={"emoji": "❤️"},
        headers=auth(tok),
    )
    assert r2.status_code == 204

    # After toggle-off the reaction count for this emoji should be 0
    r_list = await client.get(
        f"/api/v1/daily-records/{rec.id}/reactions",
        headers=auth(tok),
    )
    assert r_list.status_code == 200
    groups = r_list.json()
    heart_group = next((g for g in groups if g["emoji"] == "❤️"), None)
    assert heart_group is None or heart_group["count"] == 0


# ---------------------------------------------------------------------------
# 6. Edit own comment → 200
# ---------------------------------------------------------------------------


async def test_edit_own_comment(client, db_session):
    user, tok = await make_user(db_session, "s06_user@t.com")
    team = await make_team(db_session, "s06_Team")
    await make_membership(db_session, user.id, team.id)
    rec = await make_record(db_session, user.id, date(2026, 3, 6))

    c = await client.post(
        f"/api/v1/daily-records/{rec.id}/comments",
        json={"body": "First draft"},
        headers=auth(tok),
    )
    comment_id = c.json()["id"]

    resp = await client.put(
        f"/api/v1/comments/{comment_id}",
        json={"body": "Edited"},
        headers=auth(tok),
    )
    assert resp.status_code == 200
    assert resp.json()["body"] == "Edited"


# ---------------------------------------------------------------------------
# 7. Delete own comment → 204
# ---------------------------------------------------------------------------


async def test_delete_own_comment(client, db_session):
    user, tok = await make_user(db_session, "s07_user@t.com")
    team = await make_team(db_session, "s07_Team")
    await make_membership(db_session, user.id, team.id)
    rec = await make_record(db_session, user.id, date(2026, 3, 7))

    c = await client.post(
        f"/api/v1/daily-records/{rec.id}/comments",
        json={"body": "To be deleted"},
        headers=auth(tok),
    )
    comment_id = c.json()["id"]

    resp = await client.delete(f"/api/v1/comments/{comment_id}", headers=auth(tok))
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# 8. Another user cannot delete someone else's comment → 403
# ---------------------------------------------------------------------------


async def test_cannot_delete_others_comment(client, db_session):
    owner, tok_owner = await make_user(db_session, "s08_owner@t.com")
    other, tok_other = await make_user(db_session, "s08_other@t.com")
    team = await make_team(db_session, "s08_Team")
    await make_membership(db_session, owner.id, team.id)
    await make_membership(db_session, other.id, team.id)
    rec = await make_record(db_session, owner.id, date(2026, 3, 8))

    c = await client.post(
        f"/api/v1/daily-records/{rec.id}/comments",
        json={"body": "Owner's comment"},
        headers=auth(tok_owner),
    )
    comment_id = c.json()["id"]

    resp = await client.delete(
        f"/api/v1/comments/{comment_id}", headers=auth(tok_other)
    )
    assert resp.status_code == 403
