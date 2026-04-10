from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.admin_settings import AdminSettings
from app.db.models.category import Category, SelfAssessmentTag


async def seed_initial_data(db: AsyncSession):
    """Insert seed data if not already present."""
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

    await db.commit()
