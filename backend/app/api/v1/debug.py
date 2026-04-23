"""Admin-only debug endpoints for testing notification delivery.

Neither endpoint writes Notification rows, weekly-email tracking rows, or
idempotency keys. [DEBUG] prefix is enforced server-side.
"""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.engine import get_db
from app.db.models.user import User
from app.services.graph_auth import ConsentRequiredError
from app.services.graph_mail import refresh_graph_token, send_mail
from app.services.graph_teams import (
    post_channel_message,
)
from app.services.graph_teams import (
    refresh_graph_token as refresh_teams_token,
)

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
    channel_link: str
    message: str | None = None


class DebugOkResponse(BaseModel):
    ok: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_debug_prefix(text: str) -> str:
    return text if text.startswith(_DEBUG_PREFIX) else f"{_DEBUG_PREFIX} {text}"


def _parse_teams_channel_link(link: str) -> tuple[str, str]:
    """
    Parse a Teams channel deep link and return (teams_team_id, teams_channel_id).

    Expected format:
    https://teams.microsoft.com/l/channel/{channelId}/{channelName}?groupId={teamId}&...
    """
    parsed = urlparse(link)
    if parsed.scheme != "https" or parsed.netloc != "teams.microsoft.com":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="channel_link must be a valid https://teams.microsoft.com/l/channel/... URL",
        )
    parts = parsed.path.split("/")
    # path: /l/channel/{channelId}/{channelName}
    if len(parts) < 4 or parts[1:3] != ["l", "channel"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="channel_link path is invalid; expected /l/channel/{channelId}/...",
        )
    channel_id = unquote(parts[3])
    group_ids = parse_qs(parsed.query).get("groupId", [])
    if not group_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="channel_link is missing the groupId query parameter",
        )
    return group_ids[0], channel_id


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
    admin: User = Depends(require_admin),
) -> DebugOkResponse:
    """Post a test message to a Teams channel via the Graph API.

    The admin provides a Teams channel deep link; the backend parses the
    groupId (team ID) and channel ID from it and posts using the admin's
    own MS365 Graph token.
    """
    teams_team_id, teams_channel_id = _parse_teams_channel_link(body.channel_link)

    if admin.ms_graph_refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Admin account has no connected MS365 account",
        )

    try:
        access_token, _ = await refresh_teams_token(admin.ms_graph_refresh_token)
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

    message_text = (
        body.message or "This is a test message from TeamTakt admin debug tools."
    )
    # Prepend the [DEBUG] banner as a standalone block, then append the
    # user-supplied HTML verbatim. This avoids double-wrapping arbitrary HTML
    # in a <p> tag while still guaranteeing the prefix is present.
    html_body = f"<p><strong>{_DEBUG_PREFIX}</strong></p>{message_text}"

    try:
        await post_channel_message(
            access_token=access_token,
            teams_team_id=teams_team_id,
            teams_channel_id=teams_channel_id,
            html_body=html_body,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Teams message delivery failed: {exc}",
        ) from exc

    return DebugOkResponse()
