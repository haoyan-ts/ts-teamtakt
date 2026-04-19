from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.db.models.absence import ABSENCE_TYPE_UUIDS, AbsenceType
from app.db.models.admin_settings import AdminSettings
from app.db.models.category import Category, SelfAssessmentTag
from app.db.models.user import User

_ADMIN_PASSWORD_DEV_DEFAULT = "ChangeMe_DevOnly!"  # never use in production


async def seed_initial_data(db: AsyncSession):
    """Insert seed data if not already present."""
    for name, uid in ABSENCE_TYPE_UUIDS.items():
        existing = await db.execute(select(AbsenceType).where(AbsenceType.name == name))
        if not existing.scalar_one_or_none():
            db.add(AbsenceType(id=uid, name=name, is_active=True))

    tags = ["OKR", "Routine", "Team Contribution", "Company Contribution"]
    for name in tags:
        existing = await db.execute(
            select(SelfAssessmentTag).where(SelfAssessmentTag.name == name)
        )
        if not existing.scalar_one_or_none():
            db.add(SelfAssessmentTag(id=uuid4(), name=name, is_active=True))

    initial_categories = ["OKR", "Routine", "Interrupt"]
    for i, name in enumerate(initial_categories):
        existing = await db.execute(select(Category).where(Category.name == name))
        if not existing.scalar_one_or_none():
            db.add(Category(id=uuid4(), name=name, is_active=True, sort_order=i))

    existing = await db.execute(
        select(AdminSettings).where(AdminSettings.key == "output_language")
    )
    if not existing.scalar_one_or_none():
        db.add(AdminSettings(id=uuid4(), key="output_language", value="ja"))

    if settings.ADMIN_EMAIL:
        existing_admin = await db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        if not existing_admin.scalar_one_or_none():
            raw_password = settings.ADMIN_PASSWORD or _ADMIN_PASSWORD_DEV_DEFAULT
            db.add(
                User(
                    id=uuid4(),
                    email=settings.ADMIN_EMAIL,
                    display_name="Admin",
                    is_admin=True,
                    allow_local_login=True,
                    password_hash=hash_password(raw_password),
                )
            )

    await db.commit()
