"""Holiday calendar management endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user, require_admin
from app.db.engine import get_db
from app.db.models.notification_preference import HolidayCalendar
from app.db.models.user import User

router = APIRouter(prefix="/holidays", tags=["holidays"])


class HolidayResponse(BaseModel):
    id: uuid.UUID
    date: date
    name: str
    source: str
    is_workday: bool

    model_config = {"from_attributes": True}


class HolidayCreate(BaseModel):
    date: date
    name: str
    source: str = "admin"
    is_workday: bool = False


@router.get("", response_model=list[HolidayResponse])
async def list_holidays(
    year: int = Query(..., ge=2000, le=2100),
    _user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(HolidayCalendar)
        .where(
            HolidayCalendar.date >= date(year, 1, 1),
            HolidayCalendar.date <= date(year, 12, 31),
        )
        .order_by(HolidayCalendar.date)
    )
    return [HolidayResponse.model_validate(h) for h in r.scalars().all()]


@router.post("", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    body: HolidayCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(HolidayCalendar).where(HolidayCalendar.date == body.date)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holiday already exists for this date",
        )

    h = HolidayCalendar(
        id=uuid.uuid4(),
        date=body.date,
        name=body.name,
        source=body.source,
        is_workday=body.is_workday,
    )
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return HolidayResponse.model_validate(h)


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(HolidayCalendar).where(HolidayCalendar.id == holiday_id)
    )
    h = r.scalar_one_or_none()
    if h is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found"
        )
    await db.delete(h)
    await db.commit()


@router.get("/sync", status_code=status.HTTP_200_OK)
async def sync_holidays(
    year: int = Query(..., ge=2000, le=2100),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync Japanese national holidays from external API.
    Uses https://holidays-jp.github.io/api/v1/{year}/date.json (free, no auth).
    Falls back gracefully on error.
    """
    import httpx

    url = f"https://holidays-jp.github.io/api/v1/{year}/date.json"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url)
        resp.raise_for_status()
        holidays_data: dict[str, str] = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch holidays: {exc}",
        )

    created = 0
    updated = 0
    for date_str, name in holidays_data.items():
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            continue

        r = await db.execute(select(HolidayCalendar).where(HolidayCalendar.date == d))
        existing = r.scalar_one_or_none()
        if existing:
            existing.name = name
            existing.source = "external"
            updated += 1
        else:
            db.add(
                HolidayCalendar(
                    id=uuid.uuid4(),
                    date=d,
                    name=name,
                    source="external",
                    is_workday=False,
                )
            )
            created += 1

    await db.commit()
    return {"synced_year": year, "created": created, "updated": updated}
