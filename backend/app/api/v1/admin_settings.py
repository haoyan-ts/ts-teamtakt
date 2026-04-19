from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.engine import get_db
from app.db.models.admin_settings import AdminSettings
from app.db.models.user import User
from app.db.schemas.admin_settings import AdminSettingsResponse, AdminSettingsUpdate

router = APIRouter(tags=["admin-settings"])

_OUTPUT_LANGUAGE_KEY = "output_language"


@router.get("/admin/settings", response_model=AdminSettingsResponse)
async def get_admin_settings(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminSettingsResponse:
    result = await db.execute(
        select(AdminSettings).where(AdminSettings.key == _OUTPUT_LANGUAGE_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin settings not initialised",
        )
    return AdminSettingsResponse(output_language=row.value)


@router.patch("/admin/settings", response_model=AdminSettingsResponse)
async def update_admin_settings(
    body: AdminSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminSettingsResponse:
    result = await db.execute(
        select(AdminSettings).where(AdminSettings.key == _OUTPUT_LANGUAGE_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin settings not initialised",
        )

    if body.output_language is not None:
        row.value = body.output_language

    await db.commit()
    await db.refresh(row)
    return AdminSettingsResponse(output_language=row.value)
