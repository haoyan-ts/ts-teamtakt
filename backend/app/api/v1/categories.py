import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user, require_admin
from app.db.engine import get_db
from app.db.models.category import (
    BlockerType,
    Category,
    SelfAssessmentTag,
    WorkType,
)
from app.db.models.user import User
from app.db.schemas.category import (
    BlockerTypeCreate,
    BlockerTypeResponse,
    BlockerTypeUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    TagCreate,
    TagResponse,
    TagUpdate,
    WorkTypeCreate,
    WorkTypeResponse,
    WorkTypeUpdate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@router.post(
    "/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
async def create_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    cat = Category(
        id=uuid.uuid4(), name=body.name, sort_order=body.sort_order, is_active=True
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return CategoryResponse(
        id=cat.id,
        name=cat.name,
        is_active=cat.is_active,
        sort_order=cat.sort_order,
        sub_types=[],
    )


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if include_inactive and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    q = select(Category)
    if not include_inactive:
        q = q.where(Category.is_active.is_(True))
    result = await db.execute(q.order_by(Category.sort_order))
    categories = result.scalars().all()

    out = []
    for cat in categories:
        out.append(
            CategoryResponse(
                id=cat.id,
                name=cat.name,
                is_active=cat.is_active,
                sort_order=cat.sort_order,
                sub_types=[],
            )
        )
    return out


@router.patch("/categories/{cat_id}", response_model=CategoryResponse)
async def update_category(
    cat_id: uuid.UUID,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    if body.name is not None:
        cat.name = body.name
    if body.sort_order is not None:
        cat.sort_order = body.sort_order
    if body.is_active is not None:
        cat.is_active = body.is_active

    await db.commit()
    await db.refresh(cat)

    return CategoryResponse(
        id=cat.id,
        name=cat.name,
        is_active=cat.is_active,
        sort_order=cat.sort_order,
        sub_types=[],
    )


# ---------------------------------------------------------------------------
# Work Types
# ---------------------------------------------------------------------------


@router.post(
    "/work-types",
    response_model=WorkTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_type(
    body: WorkTypeCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    wt = WorkType(
        id=uuid.uuid4(), name=body.name, sort_order=body.sort_order, is_active=True
    )
    db.add(wt)
    await db.commit()
    await db.refresh(wt)
    return WorkTypeResponse.model_validate(wt)


@router.get("/work-types", response_model=list[WorkTypeResponse])
async def list_work_types(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if include_inactive and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    q = select(WorkType)
    if not include_inactive:
        q = q.where(WorkType.is_active.is_(True))
    result = await db.execute(q.order_by(WorkType.sort_order))
    return [WorkTypeResponse.model_validate(wt) for wt in result.scalars().all()]


@router.patch("/work-types/{wt_id}", response_model=WorkTypeResponse)
async def update_work_type(
    wt_id: uuid.UUID,
    body: WorkTypeUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(WorkType).where(WorkType.id == wt_id))
    wt = result.scalar_one_or_none()
    if wt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="WorkType not found"
        )

    if body.name is not None:
        wt.name = body.name
    if body.sort_order is not None:
        wt.sort_order = body.sort_order
    if body.is_active is not None:
        wt.is_active = body.is_active

    await db.commit()
    await db.refresh(wt)
    return WorkTypeResponse.model_validate(wt)


# ---------------------------------------------------------------------------
# Self-Assessment Tags
# ---------------------------------------------------------------------------


@router.post(
    "/self-assessment-tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tag(
    body: TagCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    tag = SelfAssessmentTag(id=uuid.uuid4(), name=body.name, is_active=True)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return TagResponse.model_validate(tag)


@router.get("/self-assessment-tags", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(SelfAssessmentTag).where(SelfAssessmentTag.is_active)
    )
    return [TagResponse.model_validate(t) for t in result.scalars().all()]


@router.patch("/self-assessment-tags/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: uuid.UUID,
    body: TagUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(SelfAssessmentTag).where(SelfAssessmentTag.id == tag_id)
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        )

    if body.name is not None:
        tag.name = body.name
    if body.is_active is not None:
        tag.is_active = body.is_active

    await db.commit()
    await db.refresh(tag)
    return TagResponse.model_validate(tag)


# ---------------------------------------------------------------------------
# Blocker Types
# ---------------------------------------------------------------------------


@router.post(
    "/blocker-types",
    response_model=BlockerTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_blocker_type(
    body: BlockerTypeCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    bt = BlockerType(id=uuid.uuid4(), name=body.name, is_active=True)
    db.add(bt)
    await db.commit()
    await db.refresh(bt)
    return BlockerTypeResponse.model_validate(bt)


@router.get("/blocker-types", response_model=list[BlockerTypeResponse])
async def list_blocker_types(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_active_user),
):
    result = await db.execute(
        select(BlockerType).where(BlockerType.is_active.is_(True))
    )
    return [BlockerTypeResponse.model_validate(bt) for bt in result.scalars().all()]


@router.patch("/blocker-types/{bt_id}", response_model=BlockerTypeResponse)
async def update_blocker_type(
    bt_id: uuid.UUID,
    body: BlockerTypeUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(BlockerType).where(BlockerType.id == bt_id))
    bt = result.scalar_one_or_none()
    if bt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="BlockerType not found"
        )

    if body.name is not None:
        bt.name = body.name
    if body.is_active is not None:
        bt.is_active = body.is_active

    await db.commit()
    await db.refresh(bt)
    return BlockerTypeResponse.model_validate(bt)
