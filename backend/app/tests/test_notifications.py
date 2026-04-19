"""Tests for notification endpoints (p13).

Key invariants tested:
- List notifications (all and unread-only)
- Mark single notification as read
- Mark all notifications as read
- Notification preferences CRUD (seed defaults + update)
- User cannot see another user's notifications
"""

from datetime import UTC, datetime

from app.core.security import create_access_token
from app.db.models.notification import Notification
from app.db.models.team import Team, TeamMembership, TeamSettings
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def make_user(db, email):
    user = User(email=email, display_name=email.split("@")[0])
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


async def make_notification(
    db, user_id, *, is_read=False, trigger_type="edit_window_closing"
):
    n = Notification(
        user_id=user_id,
        trigger_type=trigger_type,
        title="Test notification",
        body="Test body",
        is_read=is_read,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. List own notifications
# ---------------------------------------------------------------------------


async def test_list_notifications(client, db_session):
    user, tok = await make_user(db_session, "n01_user@t.com")
    team = await make_team(db_session, "n01_Team")
    await make_membership(db_session, user.id, team.id)
    await make_notification(db_session, user.id)

    resp = await client.get("/api/v1/notifications", headers=auth(tok))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(n["trigger_type"] == "edit_window_closing" for n in data)


# ---------------------------------------------------------------------------
# 2. List unread only
# ---------------------------------------------------------------------------


async def test_list_unread_only(client, db_session):
    user, tok = await make_user(db_session, "n02_user@t.com")
    team = await make_team(db_session, "n02_Team")
    await make_membership(db_session, user.id, team.id)
    await make_notification(db_session, user.id, is_read=False)
    await make_notification(db_session, user.id, is_read=True)

    resp = await client.get(
        "/api/v1/notifications", params={"unread_only": True}, headers=auth(tok)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(not n["is_read"] for n in data)


# ---------------------------------------------------------------------------
# 3. Mark single notification as read
# ---------------------------------------------------------------------------


async def test_mark_notification_read(client, db_session):
    user, tok = await make_user(db_session, "n03_user@t.com")
    team = await make_team(db_session, "n03_Team")
    await make_membership(db_session, user.id, team.id)
    notif = await make_notification(db_session, user.id, is_read=False)

    resp = await client.patch(
        f"/api/v1/notifications/{notif.id}/read", headers=auth(tok)
    )
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


# ---------------------------------------------------------------------------
# 4. Mark all notifications as read
# ---------------------------------------------------------------------------


async def test_mark_all_read(client, db_session):
    user, tok = await make_user(db_session, "n04_user@t.com")
    team = await make_team(db_session, "n04_Team")
    await make_membership(db_session, user.id, team.id)
    await make_notification(db_session, user.id, is_read=False)
    await make_notification(db_session, user.id, is_read=False)

    resp = await client.post("/api/v1/notifications/read-all", headers=auth(tok))
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/notifications", headers=auth(tok))
    data = list_resp.json()
    assert all(n["is_read"] for n in data)


# ---------------------------------------------------------------------------
# 5. User cannot read another user's notification
# ---------------------------------------------------------------------------


async def test_cannot_read_others_notification(client, db_session):
    owner, _ = await make_user(db_session, "n05_owner@t.com")
    other, tok_other = await make_user(db_session, "n05_other@t.com")
    team = await make_team(db_session, "n05_Team")
    await make_membership(db_session, owner.id, team.id)
    await make_membership(db_session, other.id, team.id)
    notif = await make_notification(db_session, owner.id)

    resp = await client.patch(
        f"/api/v1/notifications/{notif.id}/read", headers=auth(tok_other)
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 6. Unread count endpoint
# ---------------------------------------------------------------------------


async def test_unread_count(client, db_session):
    user, tok = await make_user(db_session, "n06_user@t.com")
    team = await make_team(db_session, "n06_Team")
    await make_membership(db_session, user.id, team.id)
    await make_notification(db_session, user.id, is_read=False)
    await make_notification(db_session, user.id, is_read=False)
    await make_notification(db_session, user.id, is_read=True)

    resp = await client.get("/api/v1/notifications/unread-count", headers=auth(tok))
    assert resp.status_code == 200
    assert resp.json()["count"] >= 2


# ---------------------------------------------------------------------------
# 7. Get notification preferences (seeds defaults)
# ---------------------------------------------------------------------------


async def test_get_preferences_seeds_defaults(client, db_session):
    user, tok = await make_user(db_session, "n07_user@t.com")
    team = await make_team(db_session, "n07_Team")
    await make_membership(db_session, user.id, team.id)

    resp = await client.get("/api/v1/notification-preferences", headers=auth(tok))
    assert resp.status_code == 200
    prefs = resp.json()
    assert isinstance(prefs, list)
    assert len(prefs) > 0
    assert all("trigger_type" in p for p in prefs)


# ---------------------------------------------------------------------------
# 8. Update notification preferences
# ---------------------------------------------------------------------------


async def test_update_preferences(client, db_session):
    user, tok = await make_user(db_session, "n08_user@t.com")
    team = await make_team(db_session, "n08_Team")
    await make_membership(db_session, user.id, team.id)

    # Seed defaults first
    await client.get("/api/v1/notification-preferences", headers=auth(tok))

    # Update
    payload = {
        "preferences": [
            {
                "trigger_type": "edit_window_closing",
                "channel_email": True,
                "channel_teams": False,
            }
        ]
    }
    resp = await client.put(
        "/api/v1/notification-preferences", json=payload, headers=auth(tok)
    )
    assert resp.status_code == 200
