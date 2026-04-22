"""
Shared Microsoft Graph API authentication helpers.

Provides token refresh used by both graph_mail and graph_teams.
"""

from __future__ import annotations

import base64
import json

import httpx

from app.config import settings

_GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_GRAPH_PHOTO_URL = "https://graph.microsoft.com/v1.0/me/photo/$value"

# Single consent scope used for all delegated Graph operations.
# User.Read is required for /me/photo; Mail.Send and ChannelMessage.Send for
# outbound notifications.
MS365_GRAPH_SCOPE = (
    "https://graph.microsoft.com/Mail.Send "
    "https://graph.microsoft.com/ChannelMessage.Send "
    "https://graph.microsoft.com/User.Read "
    "offline_access"
)

# Minimal scope needed to read the profile photo.
_PHOTO_SCOPE = "https://graph.microsoft.com/User.Read offline_access"

# Azure AD error codes that mean the user must re-consent before we can
# get tokens for the requested scope.
_CONSENT_REQUIRED_CODES = {65001, 70011, 70043}


class ConsentRequiredError(RuntimeError):
    """Raised when the stored refresh token lacks the requested scope consent."""


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
        # Detect Azure AD consent / scope errors so callers can prompt re-auth
        # instead of surfacing a generic 502.
        try:
            err_body = resp.json()
        except (json.JSONDecodeError, ValueError):
            err_body = {}
        error_codes: list[int] = err_body.get("error_codes") or []
        if any(c in _CONSENT_REQUIRED_CODES for c in error_codes) or err_body.get(
            "error"
        ) in {"invalid_grant", "interaction_required"}:
            raise ConsentRequiredError(
                "MS365 consent required — please reconnect your account"
            )
        raise RuntimeError(f"Token refresh failed: {resp.text}")
    data = resp.json()
    new_refresh = data.get("refresh_token") or refresh_token
    return data["access_token"], new_refresh


async def fetch_ms365_avatar(refresh_token: str) -> tuple[str, str]:
    """
    Fetch the MS365 profile photo for the authenticated user.
    Returns (data_url, new_refresh_token).
    The data_url is a base64-encoded data URI (e.g. 'data:image/jpeg;base64,...').
    Raises RuntimeError if no photo is available or fetch fails.
    """
    access_token, new_refresh_token = await refresh_graph_token(
        refresh_token, _PHOTO_SCOPE
    )
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            _GRAPH_PHOTO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code == 404:
        raise RuntimeError("No profile photo set in MS365")
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch profile photo: {resp.status_code}")

    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    encoded = base64.b64encode(resp.content).decode("ascii")
    data_url = f"data:{content_type};base64,{encoded}"
    return data_url, new_refresh_token
