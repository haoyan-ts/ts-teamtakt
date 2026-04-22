"""
Shared Microsoft Graph API authentication helpers.

Provides token refresh used by both graph_mail and graph_teams.
"""

from __future__ import annotations

import httpx

from app.config import settings

_GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


async def refresh_graph_token(refresh_token: str, scope: str) -> tuple[str, str]:
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
                "scope": scope,
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Token refresh failed: {resp.text}")
    data = resp.json()
    return data["access_token"], data["refresh_token"]
