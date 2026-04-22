import base64
import hashlib
import secrets
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import oauth_state
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import create_access_token, verify_password
from app.core.token_encryption import decrypt_token, encrypt_token
from app.db.engine import get_db
from app.db.models.team import Team, TeamMembership
from app.db.models.user import User
from app.services.graph_auth import MS365_GRAPH_SCOPE, verify_id_token

router = APIRouter(prefix="/auth", tags=["auth"])

MICROSOFT_AUTHORIZE_URL = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
)
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


@router.get("/login")
async def login():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(32)
    oauth_state.store_state(state, code_verifier)
    authorize_url = MICROSOFT_AUTHORIZE_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    params = {
        "client_id": settings.AZURE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "scope": "openid profile email Mail.Send ChannelMessage.Send User.Read offline_access",
        "response_mode": "query",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(url=f"{authorize_url}?{urlencode(params)}", status_code=307)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    entry = oauth_state.consume_state(state)
    if entry is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired state parameter"
        )

    token_url = MICROSOFT_TOKEN_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            token_url,
            data={
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.AZURE_REDIRECT_URI,
                "code_verifier": entry["code_verifier"],
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    token_data = response.json()
    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No id_token in response")

    claims = await verify_id_token(id_token)
    email = claims.get("email") or claims.get("preferred_username")
    display_name = claims.get("name") or email
    if not email:
        raise HTTPException(status_code=400, detail="No email in token claims")

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh_token in response")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            display_name=display_name,
            is_leader=False,
            is_admin=bool(settings.ADMIN_EMAIL and settings.ADMIN_EMAIL == email),
            preferred_locale="en",
        )
        db.add(user)
    user.ms_graph_refresh_token = refresh_token
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(
        {"sub": str(user.id), "is_leader": user.is_leader, "is_admin": user.is_admin}
    )
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/login?token={access_token}", status_code=307
    )


@router.post("/logout")
async def logout():
    return {"message": "Logged out"}


class LocalLoginRequest(BaseModel):
    email: str
    password: str


_INVALID_CREDENTIALS = HTTPException(
    status_code=401,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post("/local-login")
@limiter.limit("5/15minute")
async def local_login(
    request: Request,
    body: LocalLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Generic rejection — never reveal whether the email exists or why login failed
    if user is None or not user.allow_local_login or user.password_hash is None:
        raise _INVALID_CREDENTIALS

    if not verify_password(body.password, user.password_hash):
        raise _INVALID_CREDENTIALS

    access_token = create_access_token(
        {"sub": str(user.id), "is_leader": user.is_leader, "is_admin": user.is_admin}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TeamMembership, Team)
        .join(Team, TeamMembership.team_id == Team.id)
        .where(
            TeamMembership.user_id == user.id,
            TeamMembership.left_at.is_(None),
        )
    )
    row = result.first()
    team_data = None
    if row:
        _, team = row
        team_data = {"id": str(team.id), "name": team.name}

    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "is_leader": user.is_leader,
        "is_admin": user.is_admin,
        "preferred_locale": user.preferred_locale,
        "ms365_connected": user.ms_graph_refresh_token is not None,
        "avatar_url": user.avatar_url,
        "team": team_data,
        "lobby": team_data is None and not user.is_admin,
        "github_linked": user.github_access_token_enc is not None,
        "github_login": user.github_login,
    }


# ---------------------------------------------------------------------------
# MS365 delegated-permission reconnect / disconnect
# ---------------------------------------------------------------------------


@router.get("/ms365/reconnect")
async def ms365_reconnect(
    current_user: User = Depends(get_current_user),
):
    """Redirect the authenticated user to MS365 consent (re-consent after token revocation)."""
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(32)
    oauth_state.store_state(state, code_verifier, user_id=str(current_user.id))
    authorize_url = MICROSOFT_AUTHORIZE_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    params = {
        "client_id": settings.AZURE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.AZURE_MS365_RECONNECT_REDIRECT_URI,
        "scope": MS365_GRAPH_SCOPE,
        "response_mode": "query",
        "state": state,
        "prompt": "consent",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(url=f"{authorize_url}?{urlencode(params)}", status_code=307)


@router.get("/ms365/reconnect/callback")
async def ms365_reconnect_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange code for Graph tokens and persist the refresh token."""
    entry = oauth_state.consume_state(state)
    if entry is None or entry["user_id"] is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired state parameter"
        )

    token_url = MICROSOFT_TOKEN_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            token_url,
            data={
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.AZURE_MS365_RECONNECT_REDIRECT_URI,
                "scope": MS365_GRAPH_SCOPE,
                "code_verifier": entry["code_verifier"],
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    token_data = response.json()
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh_token in response")

    user_uuid = uuid.UUID(entry["user_id"])
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.ms_graph_refresh_token = refresh_token
    await db.commit()

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/settings/profile?ms365=connected", status_code=307
    )


@router.delete("/ms365/disconnect")
async def ms365_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the stored MS Graph refresh token for the current user."""
    current_user.ms_graph_refresh_token = None
    await db.commit()
    return {"ms365_connected": False}


# ---------------------------------------------------------------------------
# GitHub OAuth account linking
# ---------------------------------------------------------------------------

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_API_USER_URL = "https://api.github.com/user"
_GITHUB_API_REVOKE_URL = "https://api.github.com/applications/{client_id}/token"


@router.get("/github/authorize")
async def github_authorize(
    current_user: User = Depends(get_current_user),
):
    """Redirect the authenticated user to GitHub's OAuth authorization page."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    state = secrets.token_urlsafe(32)
    oauth_state.store_github_state(state, user_id=str(current_user.id))

    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": "repo read:user",
        "state": state,
    }
    return {"url": f"{_GITHUB_AUTHORIZE_URL}?{urlencode(params)}"}


@router.get("/github/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange the GitHub OAuth code for an access token and store it encrypted."""
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    entry = oauth_state.consume_github_state(state)
    if entry is None:
        raise HTTPException(
            status_code=400, detail="Invalid or expired state parameter"
        )

    # Exchange code for access token (PKCE included)
    # GitHub API base URL is hardcoded — never derived from user input (OWASP A10)
    async with httpx.AsyncClient() as http_client:
        token_resp = await http_client.post(
            _GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange code for token: {token_resp.text}",
        )

    token_data = token_resp.json()
    if "error" in token_data:
        raise HTTPException(
            status_code=400,
            detail=f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}",
        )

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=400, detail="No access_token in GitHub response"
        )

    # Fetch the GitHub username
    async with httpx.AsyncClient() as http_client:
        user_resp = await http_client.get(
            _GITHUB_API_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

    if user_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub user info")

    github_login = user_resp.json().get("login")

    # Encrypt the token at rest (OWASP A02)
    enc_key = settings.GITHUB_TOKEN_ENCRYPTION_KEY
    if enc_key:
        token_enc, token_iv = encrypt_token(access_token, enc_key)
    else:
        # Dev/local fallback — store plain when key is not configured
        token_enc, token_iv = access_token, ""

    user_uuid = uuid.UUID(entry["user_id"])
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.github_access_token_enc = token_enc
    user.github_token_iv = token_iv
    user.github_login = github_login
    await db.commit()

    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/settings/profile?github=connected",
        status_code=307,
    )


@router.delete("/github/unlink")
async def github_unlink(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the stored GitHub OAuth token and unlink the account."""
    if not current_user.github_access_token_enc:
        raise HTTPException(status_code=400, detail="GitHub account is not linked")

    # Attempt server-side token revocation at GitHub
    if settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET:
        enc_key = settings.GITHUB_TOKEN_ENCRYPTION_KEY
        try:
            if enc_key and current_user.github_token_iv:
                raw_token = decrypt_token(
                    current_user.github_access_token_enc,
                    current_user.github_token_iv,
                    enc_key,
                )
            else:
                raw_token = current_user.github_access_token_enc

            revoke_url = _GITHUB_API_REVOKE_URL.format(
                client_id=settings.GITHUB_CLIENT_ID
            )
            async with httpx.AsyncClient() as http_client:
                await http_client.request(
                    "DELETE",
                    revoke_url,
                    auth=(settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET),
                    json={"access_token": raw_token},
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
        except Exception:
            # Revocation failure is non-fatal — still clear locally
            pass

    current_user.github_access_token_enc = None
    current_user.github_token_iv = None
    current_user.github_login = None
    await db.commit()
    return {"github_linked": False}
