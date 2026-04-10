"""
Social Layer API — comments, reactions, activity feed, WebSocket.

Rate limits:
  - Reactions: 30 per minute per user (toggle-off on duplicate = 204, not 4xx)

WebSocket:
  - WS /ws — auth via ?token= query param
  - Subscribes to "team:{team_id}" (default) and "all" (if scope=all)
  - Broadcasts: record.created/updated, comment.created/updated/deleted,
    reaction.added/removed
  - Payloads use the same visibility filter as REST (day_load/blocker_text stripped)
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import verify_token
from app.core.ws_manager import ws_manager
from app.db.engine import async_session_factory, get_db
from app.db.models.daily_record import DailyRecord
from app.db.models.social import Comment, Reaction
from app.db.models.task_entry import TaskEntry, TaskEntrySelfAssessmentTag
from app.db.models.team import TeamMembership
from app.db.models.user import User
from app.db.schemas.social import (
    CommentCreate,
    CommentRead,
    CommentUpdate,
    FeedItemRead,
    FeedTaskEntry,
    ReactionCreate,
    ReactionGroupRead,
)
from app.services.notification import NotificationService

router = APIRouter(tags=["social"])

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Comment helpers
# ---------------------------------------------------------------------------


async def _build_comment_read(comment: Comment, db: AsyncSession) -> CommentRead:
    author = await db.scalar(select(User).where(User.id == comment.author_id))
    author_name = author.display_name if author else "Unknown"

    # Load direct replies (one level — deeper threading resolved client-side via id)
    replies_result = await db.execute(
        select(Comment)
        .where(Comment.parent_comment_id == comment.id)
        .order_by(Comment.created_at)
    )
    replies = [await _build_comment_read(r, db) for r in replies_result.scalars().all()]

    return CommentRead(
        id=comment.id,
        daily_record_id=comment.daily_record_id,
        parent_comment_id=comment.parent_comment_id,
        author_id=comment.author_id,
        author_name=author_name,
        body=comment.body,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=replies,
    )


# ---------------------------------------------------------------------------
# Comment endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/daily-records/{record_id}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=CommentRead,
)
async def add_comment(
    record_id: uuid.UUID,
    body: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.scalar(select(DailyRecord).where(DailyRecord.id == record_id))
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )

    if body.parent_comment_id is not None:
        parent = await db.scalar(
            select(Comment).where(
                Comment.id == body.parent_comment_id,
                Comment.daily_record_id == record_id,
            )
        )
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent_comment_id not found in this record",
            )

    comment = Comment(
        daily_record_id=record_id,
        parent_comment_id=body.parent_comment_id,
        author_id=current_user.id,
        body=body.body,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    # Notify record owner if commenter is not the owner
    if record.user_id != current_user.id:
        svc = NotificationService(db)
        await svc.send_batched(
            user_id=record.user_id,
            trigger_type="social_reaction",
            title_template="{count} new comment(s) on your record",
            body_template=f"{current_user.display_name} commented on your record.",
            data={"record_id": str(record_id), "comment_id": str(comment.id)},
        )

    await db.commit()
    await db.refresh(comment)

    result = await _build_comment_read(comment, db)

    # Broadcast WS event
    await _broadcast_record_channel(
        record_id,
        {"type": "comment.created", "comment": result.model_dump(mode="json")},
        db,
    )

    return result


@router.get(
    "/daily-records/{record_id}/comments",
    response_model=list[CommentRead],
)
async def list_comments(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.scalar(select(DailyRecord).where(DailyRecord.id == record_id))
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )

    # Top-level comments only; replies are nested via _build_comment_read
    result = await db.execute(
        select(Comment)
        .where(
            Comment.daily_record_id == record_id,
            Comment.parent_comment_id.is_(None),
        )
        .order_by(Comment.created_at)
    )
    return [await _build_comment_read(c, db) for c in result.scalars().all()]


@router.put("/comments/{comment_id}", response_model=CommentRead)
async def update_comment(
    comment_id: uuid.UUID,
    body: CommentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = await db.scalar(select(Comment).where(Comment.id == comment_id))
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your comment"
        )

    comment.body = body.body
    await db.commit()
    await db.refresh(comment)

    result = await _build_comment_read(comment, db)
    await _broadcast_record_channel(
        comment.daily_record_id,
        {"type": "comment.updated", "comment": result.model_dump(mode="json")},
        db,
    )
    return result


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = await db.scalar(select(Comment).where(Comment.id == comment_id))
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    # Author, admin, or leader of the record owner's team may delete
    if comment.author_id != current_user.id and not current_user.is_admin:
        if current_user.is_leader:
            # Verify leader is in same team as record owner
            record = await db.scalar(
                select(DailyRecord).where(DailyRecord.id == comment.daily_record_id)
            )
            assert record is not None
            owner_team = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == record.user_id,
                    TeamMembership.left_at.is_(None),
                )
            )
            leader_team = await db.scalar(
                select(TeamMembership).where(
                    TeamMembership.user_id == current_user.id,
                    TeamMembership.left_at.is_(None),
                )
            )
            if (
                owner_team is None
                or leader_team is None
                or owner_team.team_id != leader_team.team_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    record_id = comment.daily_record_id
    await db.delete(comment)
    await db.commit()

    await _broadcast_record_channel(
        record_id,
        {"type": "comment.deleted", "comment_id": str(comment_id)},
        db,
    )


# ---------------------------------------------------------------------------
# Reaction endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/daily-records/{record_id}/reactions",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("30/minute")
async def toggle_reaction(
    request: Request,
    record_id: uuid.UUID,
    body: ReactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.scalar(select(DailyRecord).where(DailyRecord.id == record_id))
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )

    existing = await db.scalar(
        select(Reaction).where(
            Reaction.daily_record_id == record_id,
            Reaction.user_id == current_user.id,
            Reaction.emoji == body.emoji,
        )
    )

    if existing is not None:
        # Toggle off
        await db.delete(existing)
        await db.commit()
        await _broadcast_record_channel(
            record_id,
            {
                "type": "reaction.removed",
                "record_id": str(record_id),
                "emoji": body.emoji,
                "user_id": str(current_user.id),
            },
            db,
        )
        return

    reaction = Reaction(
        daily_record_id=record_id,
        user_id=current_user.id,
        emoji=body.emoji,
    )
    db.add(reaction)

    # Notify record owner (batched)
    if record.user_id != current_user.id:
        svc = NotificationService(db)
        await svc.send_batched(
            user_id=record.user_id,
            trigger_type="social_reaction",
            title_template="{count} new reaction(s) on your record",
            body_template=f"{current_user.display_name} reacted to your record.",
            data={"record_id": str(record_id), "emoji": body.emoji},
        )

    await db.commit()
    await _broadcast_record_channel(
        record_id,
        {
            "type": "reaction.added",
            "record_id": str(record_id),
            "emoji": body.emoji,
            "user_id": str(current_user.id),
        },
        db,
    )


@router.get(
    "/daily-records/{record_id}/reactions",
    response_model=list[ReactionGroupRead],
)
async def list_reactions(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.scalar(select(DailyRecord).where(DailyRecord.id == record_id))
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )

    result = await db.execute(
        select(Reaction).where(Reaction.daily_record_id == record_id)
    )
    reactions = result.scalars().all()

    grouped: dict[str, list[uuid.UUID]] = defaultdict(list)
    for r in reactions:
        grouped[r.emoji].append(r.user_id)

    return [
        ReactionGroupRead(
            emoji=emoji,
            count=len(user_ids),
            reacted_by_me=current_user.id in user_ids,
            user_ids=user_ids,
        )
        for emoji, user_ids in grouped.items()
    ]


@router.delete(
    "/daily-records/{record_id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_reaction(
    record_id: uuid.UUID,
    emoji: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(Reaction).where(
            Reaction.daily_record_id == record_id,
            Reaction.user_id == current_user.id,
            Reaction.emoji == emoji,
        )
    )
    if existing is None:
        return  # idempotent

    await db.delete(existing)
    await db.commit()
    await _broadcast_record_channel(
        record_id,
        {
            "type": "reaction.removed",
            "record_id": str(record_id),
            "emoji": emoji,
            "user_id": str(current_user.id),
        },
        db,
    )


# ---------------------------------------------------------------------------
# Feed endpoint
# ---------------------------------------------------------------------------


@router.get("/feed", response_model=list[FeedItemRead])
async def get_feed(
    scope: str = Query(default="team", pattern="^(team|all)$"),
    cursor: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DailyRecord).order_by(DailyRecord.created_at.desc()).limit(limit)

    if cursor is not None:
        stmt = stmt.where(DailyRecord.created_at < cursor)

    if scope == "team":
        # Get current user's team members
        mem = await db.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.left_at.is_(None),
            )
        )
        if mem is None:
            return []
        member_ids_result = await db.execute(
            select(TeamMembership.user_id).where(
                TeamMembership.team_id == mem.team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        member_ids = [row[0] for row in member_ids_result.all()]
        stmt = stmt.where(DailyRecord.user_id.in_(member_ids))

    result = await db.execute(stmt)
    records = result.scalars().all()

    feed_items = []
    for record in records:
        # Load task entries for public fields
        te_result = await db.execute(
            select(TaskEntry)
            .where(TaskEntry.daily_record_id == record.id)
            .order_by(TaskEntry.sort_order)
        )
        task_entries = []
        for te in te_result.scalars().all():
            tags_result = await db.execute(
                select(TaskEntrySelfAssessmentTag).where(
                    TaskEntrySelfAssessmentTag.task_entry_id == te.id
                )
            )
            task_entries.append(
                FeedTaskEntry(
                    id=te.id,
                    category_id=te.category_id,
                    project_id=te.project_id,
                    task_description=te.task_description,
                    effort=te.effort,
                    status=te.status,
                    blocker_type_id=te.blocker_type_id,
                    # blocker_text intentionally omitted
                    carried_from_id=te.carried_from_id,
                    sort_order=te.sort_order,
                    self_assessment_tags=[
                        {
                            "self_assessment_tag_id": str(t.self_assessment_tag_id),
                            "is_primary": t.is_primary,
                        }
                        for t in tags_result.scalars().all()
                    ],
                )
            )

        # Reaction summary
        rxn_result = await db.execute(
            select(Reaction).where(Reaction.daily_record_id == record.id)
        )
        rxns = rxn_result.scalars().all()
        grouped: dict[str, list[uuid.UUID]] = defaultdict(list)
        for rxn in rxns:
            grouped[rxn.emoji].append(rxn.user_id)
        reaction_groups = [
            ReactionGroupRead(
                emoji=emoji,
                count=len(user_ids),
                reacted_by_me=current_user.id in user_ids,
                user_ids=user_ids,
            )
            for emoji, user_ids in grouped.items()
        ]

        # Comment count
        comment_count = await db.scalar(
            select(func.count(Comment.id)).where(Comment.daily_record_id == record.id)
        )

        # Record owner display name
        owner = await db.scalar(select(User).where(User.id == record.user_id))
        display_name = owner.display_name if owner else ""

        feed_items.append(
            FeedItemRead(
                id=record.id,
                user_id=record.user_id,
                display_name=display_name,
                record_date=record.record_date.isoformat(),
                day_note=record.day_note,
                task_entries=task_entries,
                comment_count=comment_count or 0,
                reactions=reaction_groups,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        )

    return feed_items


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(...),
    scope: str = Query(default="team"),
):
    """
    Auth via ?token= query param.
    Subscribe to team:{team_id} by default; also "all" if scope=all.
    """
    try:
        payload = verify_token(token)
    except HTTPException:
        await ws.close(code=4001)
        return

    user_id_str = payload.get("sub")
    if not user_id_str:
        await ws.close(code=4001)
        return

    async with async_session_factory() as db:
        import uuid as _uuid

        try:
            user_uuid = _uuid.UUID(user_id_str)
        except ValueError:
            await ws.close(code=4001)
            return

        user = await db.scalar(select(User).where(User.id == user_uuid))
        if user is None:
            await ws.close(code=4001)
            return

        mem = await db.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user.id,
                TeamMembership.left_at.is_(None),
            )
        )

    channels: list[str] = []
    if mem is not None:
        channels.append(f"team:{mem.team_id}")
    if scope == "all":
        channels.append("all")

    await ws_manager.connect(ws, channels)
    try:
        while True:
            # Heartbeat: echo back pings, ignore other messages
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws, channels)


# ---------------------------------------------------------------------------
# Broadcast helper
# ---------------------------------------------------------------------------


async def _broadcast_record_channel(
    record_id: uuid.UUID,
    payload: dict,
    db: AsyncSession,
) -> None:
    """Broadcast to the record owner's team channel and to 'all'."""
    record = await db.scalar(select(DailyRecord).where(DailyRecord.id == record_id))
    if record is None:
        return
    mem = await db.scalar(
        select(TeamMembership).where(
            TeamMembership.user_id == record.user_id,
            TeamMembership.left_at.is_(None),
        )
    )
    channels = ["all"]
    if mem is not None:
        channels.append(f"team:{mem.team_id}")
    await ws_manager.broadcast_multi(channels, payload)
