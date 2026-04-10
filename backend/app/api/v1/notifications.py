"""Notification CRUD endpoints + preferences."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user
from app.db.engine import get_db
from app.db.models.notification import Notification
from app.db.models.notification_preference import (
    TRIGGER_DEFAULTS,
    TRIGGER_TYPES,
    NotificationPreference,
)
from app.db.models.user import User

router = APIRouter(tags=["notifications"])


class NotificationResponse(BaseModel):
    id: uuid.UUID
    trigger_type: str
    title: str
    body: str | None
    data: dict | None
    batch_count: int
    is_read: bool
    created_at: str

    model_config = {"from_attributes": True}


class PreferenceResponse(BaseModel):
    trigger_type: str
    channel_email: bool
    channel_teams: bool


class PreferencesUpdate(BaseModel):
    preferences: list[PreferenceResponse]


def _notif_to_resp(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        trigger_type=n.trigger_type,
        title=n.title,
        body=n.body,
        data=n.data,
        batch_count=n.batch_count,
        is_read=n.is_read,
        created_at=n.created_at.isoformat(),
    )


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    unread_only: bool = False,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        q = q.where(~Notification.is_read)
    q = q.order_by(Notification.created_at.desc())
    r = await db.execute(q)
    return [_notif_to_resp(n) for n in r.scalars().all()]


@router.get("/notifications/unread-count")
async def unread_count(
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func

    r = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == current_user.id,
            ~Notification.is_read,
        )
    )
    return {"count": r.scalar() or 0}


@router.patch("/notifications/{notif_id}/read", response_model=NotificationResponse)
async def mark_read(
    notif_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException

    r = await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = r.scalar_one_or_none()
    if notif is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    notif.is_read = True
    await db.commit()
    await db.refresh(notif)
    return _notif_to_resp(notif)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, ~Notification.is_read)
        .values(is_read=True)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


async def _get_all_prefs(
    user_id: uuid.UUID, db: AsyncSession
) -> list[NotificationPreference]:
    """Return preferences for all trigger types, seeding defaults for missing ones."""
    r = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    existing = {p.trigger_type: p for p in r.scalars().all()}
    prefs = []
    flush_needed = False
    for tt in TRIGGER_TYPES:
        if tt in existing:
            prefs.append(existing[tt])
        else:
            em, te = TRIGGER_DEFAULTS.get(tt, (False, False))
            pref = NotificationPreference(
                id=uuid.uuid4(),
                user_id=user_id,
                trigger_type=tt,
                channel_email=em,
                channel_teams=te,
            )
            db.add(pref)
            prefs.append(pref)
            flush_needed = True
    if flush_needed:
        await db.commit()
    return prefs


@router.get("/notification-preferences", response_model=list[PreferenceResponse])
async def get_preferences(
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_all_prefs(current_user.id, db)
    return [
        PreferenceResponse(
            trigger_type=p.trigger_type,
            channel_email=p.channel_email,
            channel_teams=p.channel_teams,
        )
        for p in prefs
    ]


@router.put("/notification-preferences", response_model=list[PreferenceResponse])
async def update_preferences(
    body: PreferencesUpdate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    prefs_map = {p.trigger_type: p for p in await _get_all_prefs(current_user.id, db)}
    for upd in body.preferences:
        if upd.trigger_type in prefs_map:
            prefs_map[upd.trigger_type].channel_email = upd.channel_email
            prefs_map[upd.trigger_type].channel_teams = upd.channel_teams
    await db.commit()
    return [
        PreferenceResponse(
            trigger_type=p.trigger_type,
            channel_email=p.channel_email,
            channel_teams=p.channel_teams,
        )
        for p in prefs_map.values()
    ]
