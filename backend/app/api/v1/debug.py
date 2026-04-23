"""Admin-only debug endpoints for testing notification delivery.

Neither endpoint writes Notification rows, weekly-email tracking rows, or
idempotency keys. [DEBUG] prefix is enforced server-side.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.engine import get_db
from app.db.models.user import User
from app.services.graph_auth import ConsentRequiredError
from app.services.graph_mail import refresh_graph_token, send_mail

router = APIRouter(tags=["admin-debug"])

_DEBUG_PREFIX = "[DEBUG]"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SendEmailRequest(BaseModel):
    from_address: str
    to_address: str
    subject: str = f"{_DEBUG_PREFIX} Test Email"


class SendTeamsMessageRequest(BaseModel):
    webhook_url: str
    message: str | None = None


class DebugOkResponse(BaseModel):
    ok: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_debug_prefix(text: str) -> str:
    return text if text.startswith(_DEBUG_PREFIX) else f"{_DEBUG_PREFIX} {text}"


def _validate_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="webhook_url must use HTTPS",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/admin/debug/send-email",
    response_model=DebugOkResponse,
    status_code=status.HTTP_200_OK,
)
async def debug_send_email(
    body: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> DebugOkResponse:
    """Send a test email via the FROM user's MS365 account.

    The backend resolves `from_address` to a user in the system and uses their
    stored Graph refresh token to send. This lets admins test delivery for any
    team member, not just themselves.
    """
    result = await db.execute(select(User).where(User.email == body.from_address))
    from_user = result.scalar_one_or_none()
    if from_user is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No user found with email '{body.from_address}'",
        )
    if from_user.ms_graph_refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"User '{body.from_address}' has no connected MS365 account",
        )

    try:
        access_token, _ = await refresh_graph_token(from_user.ms_graph_refresh_token)
    except ConsentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token refresh failed: {exc}",
        ) from exc

    subject = _ensure_debug_prefix(body.subject)
    html_body = (
        f"<p><strong>{_DEBUG_PREFIX} This is a test email from TeamTakt admin debug tools.</strong></p>"
        f"<p>Sent from: {body.from_address}</p>"
        f"<p>Sent to: {body.to_address}</p>"
    )

    try:
        await send_mail(
            access_token=access_token,
            to_addresses=[body.to_address],
            subject=subject,
            html_body=html_body,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email delivery failed: {exc}",
        ) from exc

    return DebugOkResponse()


@router.post(
    "/admin/debug/send-teams-message",
    response_model=DebugOkResponse,
    status_code=status.HTTP_200_OK,
)
async def debug_send_teams_message(
    body: SendTeamsMessageRequest,
    _admin: User = Depends(require_admin),
) -> DebugOkResponse:
    """Post a test message to a Teams channel via an incoming webhook URL.

    The admin provides the full webhook URL; no stored channel config is used.
    """
    _validate_https_url(body.webhook_url)

    message_text = (
        body.message or "This is a test message from TeamTakt admin debug tools."
    )
    payload = {"text": _ensure_debug_prefix(message_text)}

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(body.webhook_url, json=payload)

    if resp.status_code not in (200, 201, 202):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Teams webhook delivery failed [{resp.status_code}]: {resp.text}",
        )

    return DebugOkResponse()
