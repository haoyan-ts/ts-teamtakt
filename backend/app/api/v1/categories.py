import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user, require_admin
from app.db.engine import get_db
from app.db.models.category import (
    BlockerType,
    Category,
    CategorySubType,
    SelfAssessmentTag,
)
from app.db.models.user import User
from app.db.schemas.category import (
    BlockerTypeCreate,
    BlockerTypeResponse,
    BlockerTypeUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    SubTypeCreate,
    SubTypeResponse,
    SubTypeUpdate,
    TagCreate,
    TagResponse,
    TagUpdate,
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
        sub_q = select(CategorySubType).where(CategorySubType.category_id == cat.id)
        if not include_inactive:
            sub_q = sub_q.where(CategorySubType.is_active.is_(True))
        sub_result = await db.execute(sub_q.order_by(CategorySubType.sort_order))
        sub_types = [
            SubTypeResponse.model_validate(st) for st in sub_result.scalars().all()
        ]
        out.append(
            CategoryResponse(
                id=cat.id,
                name=cat.name,
                is_active=cat.is_active,
                sort_order=cat.sort_order,
                sub_types=sub_types,
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

    sub_result = await db.execute(
        select(CategorySubType).where(CategorySubType.category_id == cat.id)
    )
    sub_types = [
        SubTypeResponse.model_validate(st) for st in sub_result.scalars().all()
    ]
    return CategoryResponse(
        id=cat.id,
        name=cat.name,
        is_active=cat.is_active,
        sort_order=cat.sort_order,
        sub_types=sub_types,
    )


@router.post(
    "/categories/{cat_id}/sub-types",
    response_model=SubTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sub_type(
    cat_id: uuid.UUID,
    body: SubTypeCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Category).where(Category.id == cat_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    st = CategorySubType(
        id=uuid.uuid4(),
        category_id=cat_id,
        name=body.name,
        sort_order=body.sort_order,
        is_active=True,
    )
    db.add(st)
    await db.commit()
    await db.refresh(st)
    return SubTypeResponse.model_validate(st)


@router.patch("/category-sub-types/{sub_id}", response_model=SubTypeResponse)
async def update_sub_type(
    sub_id: uuid.UUID,
    body: SubTypeUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(CategorySubType).where(CategorySubType.id == sub_id)
    )
    st = result.scalar_one_or_none()
    if st is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SubType not found"
        )

    if body.name is not None:
        st.name = body.name
    if body.sort_order is not None:
        st.sort_order = body.sort_order
    if body.is_active is not None:
        st.is_active = body.is_active

    await db.commit()
    await db.refresh(st)
    return SubTypeResponse.model_validate(st)


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
