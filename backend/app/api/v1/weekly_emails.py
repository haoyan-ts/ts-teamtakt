"""
Weekly Email Draft endpoints:
  POST /weekly-emails/draft?week_start=         — generate LLM draft
  GET  /weekly-emails/draft?week_start=         — get current draft
  PUT  /weekly-emails/draft/{id}                — member edits draft
  POST /weekly-emails/{id}/send                 — send via Graph API

Invariants:
  - Idempotency key: (user_id, week_start)
  - 5-minute cooldown between sends of the same report
  - Email sent from member's own account (delegated Mail.Send)
  - Never auto-send; member must explicitly trigger
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_active_user
from app.db.engine import get_db
from app.db.models.daily_record import DailyRecord
from app.db.models.task import DailyWorkLog
from app.db.models.team import TeamExtraCc, TeamMembership
from app.db.models.user import User
from app.db.models.weekly_report import EmailDraftStatus, WeeklyEmailDraft, WeeklyReport
from app.db.schemas.weekly_report import (
    EmailDraftBodySections,
    WeeklyEmailDraftResponse,
    WeeklyEmailDraftUpdate,
)
from app.services import graph_mail, llm

router = APIRouter(tags=["weekly-emails"])

_COOLDOWN_MINUTES = 5
_SUBJECT_FMT = "週報[{label}]・{name}"


def _week_label(week_start: date) -> str:
    week_end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%y%m%d')}-{week_end.strftime('%y%m%d')}"


def _idempotency_key(user_id: uuid.UUID, week_start: date) -> str:
    return f"{user_id}:{week_start}"


def _to_response(draft: WeeklyEmailDraft) -> WeeklyEmailDraftResponse:
    sections = draft.body_sections or {}
    return WeeklyEmailDraftResponse(
        id=draft.id,
        user_id=draft.user_id,
        week_start=draft.week_start,
        subject=draft.subject,
        body_sections=EmailDraftBodySections(
            tasks=sections.get("tasks", ""),
            successes=sections.get("successes", ""),
            next_week=sections.get("next_week", ""),
        ),
        status=draft.status.value,
        idempotency_key=draft.idempotency_key,
        sent_at=draft.sent_at.isoformat() if draft.sent_at else None,
        error_message=draft.error_message,
    )


async def _get_output_language(db: AsyncSession) -> str:
    from app.db.models.admin_settings import AdminSettings

    r = await db.execute(
        select(AdminSettings).where(AdminSettings.key == "output_language")
    )
    setting = r.scalar_one_or_none()
    if setting and isinstance(setting.value, str):
        return setting.value
    return "ja"


@router.post(
    "/weekly-emails/draft",
    response_model=WeeklyEmailDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_refresh_draft(
    week_start: date = Query(...),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate (or re-generate) an LLM email draft for the given week."""
    # Fetch weekly report for context
    wr_r = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.user_id == current_user.id,
            WeeklyReport.week_start == week_start,
        )
    )
    report = wr_r.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Weekly report not generated yet. Call /weekly-reports/generate first.",
        )

    # Fetch day_insights and blocker_text for the week (raw, for LLM)
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    recs_r = await db.execute(
        select(DailyRecord).where(
            DailyRecord.user_id == current_user.id,
            DailyRecord.record_date.in_(week_dates),
        )
    )
    records = recs_r.scalars().all()
    record_ids = [r.id for r in records]

    lt_r = await db.execute(
        select(DailyWorkLog).where(DailyWorkLog.daily_record_id.in_(record_ids))
        if record_ids
        else select(DailyWorkLog).where(false())
    )
    work_logs = lt_r.scalars().all()

    day_insights = [r.day_insight for r in records if r.day_insight]
    blocker_texts = [log.blocker_text for log in work_logs if log.blocker_text]

    rd = report.data
    output_language = await _get_output_language(db)

    body_sections = await llm.generate_email_draft(
        display_name=current_user.display_name,
        week_label=_week_label(week_start),
        output_language=output_language,
        days_reported=rd.get("days_reported", 0),
        total_tasks=rd.get("total_tasks", 0),
        avg_day_load=rd.get("avg_day_load", 0.0),
        category_breakdown=rd.get("category_breakdown", {}),
        top_projects=rd.get("top_projects", []),
        carry_overs=rd.get("carry_overs", []),
        blockers=rd.get("blockers", []),
        day_insights=day_insights,
        blocker_texts=blocker_texts,
    )

    idem_key = _idempotency_key(current_user.id, week_start)
    subject = _SUBJECT_FMT.format(
        label=_week_label(week_start), name=current_user.display_name
    )

    existing_r = await db.execute(
        select(WeeklyEmailDraft).where(WeeklyEmailDraft.idempotency_key == idem_key)
    )
    draft = existing_r.scalar_one_or_none()

    if draft:
        draft.subject = subject
        draft.body_sections = body_sections
        if draft.status != EmailDraftStatus.sent:
            draft.status = EmailDraftStatus.draft
    else:
        draft = WeeklyEmailDraft(
            user_id=current_user.id,
            week_start=week_start,
            subject=subject,
            body_sections=body_sections,
            status=EmailDraftStatus.draft,
            idempotency_key=idem_key,
        )
        db.add(draft)

    await db.commit()
    await db.refresh(draft)
    return _to_response(draft)


@router.get("/weekly-emails/draft", response_model=list[WeeklyEmailDraftResponse])
async def list_drafts(
    week_start: date | None = Query(None),
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(WeeklyEmailDraft).where(WeeklyEmailDraft.user_id == current_user.id)
    if week_start:
        q = q.where(WeeklyEmailDraft.week_start == week_start)
    q = q.order_by(WeeklyEmailDraft.week_start.desc())
    r = await db.execute(q)
    return [_to_response(d) for d in r.scalars().all()]


@router.put("/weekly-emails/draft/{draft_id}", response_model=WeeklyEmailDraftResponse)
async def update_draft(
    draft_id: uuid.UUID,
    body: WeeklyEmailDraftUpdate,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(WeeklyEmailDraft).where(
            WeeklyEmailDraft.id == draft_id,
            WeeklyEmailDraft.user_id == current_user.id,
        )
    )
    draft = r.scalar_one_or_none()
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found"
        )
    if draft.status == EmailDraftStatus.sent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot edit a sent draft"
        )

    if body.subject is not None:
        draft.subject = body.subject
    if body.body_sections is not None:
        draft.body_sections = body.body_sections.model_dump()

    await db.commit()
    await db.refresh(draft)
    return _to_response(draft)


@router.post("/weekly-emails/{draft_id}/send", response_model=WeeklyEmailDraftResponse)
async def send_email(
    draft_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(WeeklyEmailDraft).where(
            WeeklyEmailDraft.id == draft_id,
            WeeklyEmailDraft.user_id == current_user.id,
        )
    )
    draft = r.scalar_one_or_none()
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found"
        )

    # Idempotency: already sent?
    if draft.status == EmailDraftStatus.sent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already sent. Wait for cooldown to resend.",
        )

    # Cooldown: 5-min cooldown since last send attempt (successful or failed)
    if draft.sent_at:
        sent_at = (
            draft.sent_at if draft.sent_at.tzinfo else draft.sent_at.replace(tzinfo=UTC)
        )
        cooldown_end = sent_at + timedelta(minutes=_COOLDOWN_MINUTES)
        if datetime.now(UTC) < cooldown_end:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Cooldown active. Try again after {cooldown_end.isoformat()}.",
            )

    # Require MS Graph refresh token
    if not current_user.ms_graph_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No MS Graph token. Re-authenticate to grant Mail.Send permission.",
        )

    # Collect recipients: leader + team extra CCs
    recipients: list[str] = []
    mem_r = await db.execute(
        select(TeamMembership).where(
            TeamMembership.user_id == current_user.id,
            TeamMembership.left_at.is_(None),
        )
    )
    membership = mem_r.scalar_one_or_none()
    if membership:
        from app.db.models.user import User as UserModel

        leader_r = await db.execute(
            select(UserModel)
            .join(TeamMembership, UserModel.id == TeamMembership.user_id)
            .where(
                TeamMembership.team_id == membership.team_id,
                TeamMembership.left_at.is_(None),
                UserModel.is_leader.is_(True),
            )
        )
        for leader in leader_r.scalars().all():
            if leader.id != current_user.id:
                recipients.append(leader.email)

        cc_r = await db.execute(
            select(TeamExtraCc).where(TeamExtraCc.team_id == membership.team_id)
        )
        recipients.extend([cc.email for cc in cc_r.scalars().all()])

    if not recipients:
        recipients = [current_user.email]  # fallback: send to self

    html_body = graph_mail.build_email_html(draft.body_sections or {})

    now = datetime.now(UTC)
    draft.sent_at = now  # record attempt time before API call

    try:
        access_token, new_refresh = await graph_mail.refresh_graph_token(
            current_user.ms_graph_refresh_token
        )
        # Update stored refresh token
        current_user.ms_graph_refresh_token = new_refresh
        db.add(current_user)

        await graph_mail.send_mail(
            access_token=access_token,
            to_addresses=recipients,
            subject=draft.subject,
            html_body=html_body,
        )
        draft.status = EmailDraftStatus.sent
        draft.error_message = None
    except Exception as exc:
        draft.status = EmailDraftStatus.failed
        draft.error_message = str(exc)[:500]

    await db.commit()
    await db.refresh(draft)
    return _to_response(draft)
