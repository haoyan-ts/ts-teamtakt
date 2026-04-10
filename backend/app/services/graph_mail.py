"""
Microsoft Graph API mail service.

Sends email from the member's own MS365 account via delegated Mail.Send permission.
The user's MS Graph refresh token is stored in User.ms_graph_refresh_token.

Token refresh flow:
   POST /oauth2/v2.0/token  (grant_type=refresh_token)
   → new access_token + refresh_token
   Update stored refresh_token.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/me/sendMail"


async def refresh_graph_token(refresh_token: str) -> tuple[str, str]:
    """
    Exchange a refresh token for a new access + refresh token pair.
    Returns (access_token, new_refresh_token).
    Raises RuntimeError on failure.
    """
    url = _GRAPH_TOKEN_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            url,
            data={
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": "https://graph.microsoft.com/Mail.Send offline_access",
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Token refresh failed: {resp.text}")
    data = resp.json()
    return data["access_token"], data["refresh_token"]


async def send_mail(
    *,
    access_token: str,
    to_addresses: list[str],
    subject: str,
    html_body: str,
) -> None:
    """
    Send an email via Graph API /me/sendMail using the provided access token.
    Raises RuntimeError on failure.
    """
    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body,
            },
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in to_addresses
            ],
        },
        "saveToSentItems": True,
    }
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            _GRAPH_SEND_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=message,
        )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Graph sendMail failed [{resp.status_code}]: {resp.text}")


def build_email_html(body_sections: dict[str, str]) -> str:
    """Convert body_sections dict to simple HTML email body."""
    tasks = body_sections.get("tasks", "")
    successes = body_sections.get("successes", "")
    next_week = body_sections.get("next_week", "")

    return (
        "<html><body>"
        f"<h3>業務 (Tasks)</h3><p>{tasks}</p>"
        f"<h3>〇・× (Successes / Challenges)</h3><p>{successes}</p>"
        f"<h3>予定 (Next Week)</h3><p>{next_week}</p>"
        "</body></html>"
    )
