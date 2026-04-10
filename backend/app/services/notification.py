"""
NotificationService — creates in-app notifications and routes to email/Teams.

Channels:
  - in_app: always on
  - email: per preference (Teams in Phase 3A webhook — wired but not dispatched)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification
from app.db.models.notification_preference import (
    TRIGGER_DEFAULTS,
    NotificationPreference,
)

_SOCIAL_BATCH_WINDOW_MINUTES = 15


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def send(
        self,
        *,
        user_id: uuid.UUID,
        trigger_type: str,
        title: str,
        body: str | None = None,
        data: dict | None = None,
    ) -> Notification:
        """Create an in-app notification and check preferences for other channels."""
        notif = Notification(
            id=uuid.uuid4(),
            user_id=user_id,
            trigger_type=trigger_type,
            title=title,
            body=body,
            data=data,
            batch_count=1,
        )
        self._db.add(notif)
        await self._db.flush()

        prefs = await self._get_or_default(user_id, trigger_type)

        if prefs.channel_email:
            # Email queuing is handled by the caller (e.g., weekly report endpoint)
            # Phase 3A: queue email task here
            pass

        if prefs.channel_teams:
            # Phase 3A: queue Teams webhook message here
            pass

        return notif

    async def send_batched(
        self,
        *,
        user_id: uuid.UUID,
        trigger_type: str,
        title_template: str,
        body_template: str | None = None,
        data: dict | None = None,
    ) -> Notification:
        """
        Batch logic for social_reaction trigger.
        If a notification already exists for this user/trigger within the batch
        window, increment batch_count. Otherwise create a new one.
        """
        window_start = datetime.now(UTC) - timedelta(
            minutes=_SOCIAL_BATCH_WINDOW_MINUTES
        )
        r = await self._db.execute(
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.trigger_type == trigger_type,
                Notification.is_read.is_(False),
                Notification.created_at >= window_start,
            )
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        existing = r.scalar_one_or_none()

        if existing:
            existing.batch_count += 1
            count = existing.batch_count
            existing.title = title_template.format(count=count)
            if body_template:
                existing.body = body_template.format(count=count)
            await self._db.flush()
            return existing

        return await self.send(
            user_id=user_id,
            trigger_type=trigger_type,
            title=title_template.format(count=1),
            body=body_template.format(count=1) if body_template else None,
            data=data,
        )

    async def _get_or_default(
        self, user_id: uuid.UUID, trigger_type: str
    ) -> NotificationPreference:
        r = await self._db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.trigger_type == trigger_type,
            )
        )
        pref = r.scalar_one_or_none()
        if pref is None:
            defaults = TRIGGER_DEFAULTS.get(trigger_type, (False, False))
            pref = NotificationPreference(
                id=uuid.uuid4(),
                user_id=user_id,
                trigger_type=trigger_type,
                channel_email=defaults[0],
                channel_teams=defaults[1],
            )
            self._db.add(pref)
            await self._db.flush()
        return pref
