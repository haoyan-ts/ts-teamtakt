import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user, require_admin
from app.db.engine import get_db
from app.db.models.absence import AbsenceType
from app.db.models.user import User
from app.db.schemas.absence import (
    AbsenceTypeCreate,
    AbsenceTypeResponse,
    AbsenceTypeUpdate,
)

router = APIRouter(tags=["absence-types"])


@router.post(
    "/absence-types",
    response_model=AbsenceTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_absence_type(
    body: AbsenceTypeCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    at = AbsenceType(id=uuid.uuid4(), name=body.name, is_active=True)
    db.add(at)
    await db.commit()
    await db.refresh(at)
    return AbsenceTypeResponse.model_validate(at)


@router.get("/absence-types", response_model=list[AbsenceTypeResponse])
async def list_absence_types(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if include_inactive and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    q = select(AbsenceType)
    if not include_inactive:
        q = q.where(AbsenceType.is_active.is_(True))
    result = await db.execute(q.order_by(AbsenceType.name))
    return [AbsenceTypeResponse.model_validate(at) for at in result.scalars().all()]


@router.patch("/absence-types/{at_id}", response_model=AbsenceTypeResponse)
async def update_absence_type(
    at_id: uuid.UUID,
    body: AbsenceTypeUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(AbsenceType).where(AbsenceType.id == at_id))
    at = result.scalar_one_or_none()
    if at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AbsenceType not found"
        )

    if body.name is not None:
        at.name = body.name
    if body.is_active is not None:
        at.is_active = body.is_active

    await db.commit()
    await db.refresh(at)
    return AbsenceTypeResponse.model_validate(at)
