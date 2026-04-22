import hashlib
import hmac
import secrets
import uuid as _uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from jose import jwt as jose_jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import create_access_token, verify_password, verify_token
from app.db.engine import get_db
from app.db.models.team import Team, TeamMembership
from app.db.models.user import User
from app.services.graph_auth import MS365_GRAPH_SCOPE

router = APIRouter(prefix="/auth", tags=["auth"])

MICROSOFT_AUTHORIZE_URL = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
)
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def _generate_state() -> str:
    nonce = secrets.token_urlsafe(32)
    sig = hmac.new(
        settings.SECRET_KEY.encode(), nonce.encode(), hashlib.sha256
    ).hexdigest()
    return f"{nonce}.{sig}"


def _generate_ms365_state(user_id: str) -> str:
    """Generate a signed state for the MS365 delegated-permission OAuth flow."""
    nonce = secrets.token_urlsafe(32)
    payload = f"{user_id}:{nonce}"
    sig = hmac.new(
        settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{sig}"


def _verify_ms365_state(state: str) -> str | None:
    """Return user_id if the state is valid, else None."""
    try:
        body, sig = state.rsplit(".", 1)
        expected = hmac.new(
            settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        user_id, _nonce = body.split(":", 1)
        return user_id
    except Exception:
        return None


_MS365_GRAPH_SCOPE = MS365_GRAPH_SCOPE


def _verify_state(state: str) -> bool:
    try:
        nonce, sig = state.rsplit(".", 1)
        expected = hmac.new(
            settings.SECRET_KEY.encode(), nonce.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


@router.get("/login")
async def login():
    state = _generate_state()
    authorize_url = MICROSOFT_AUTHORIZE_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    params = {
        "client_id": settings.AZURE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "scope": "openid profile email",
        "response_mode": "query",
        "state": state,
    }
    return RedirectResponse(url=f"{authorize_url}?{urlencode(params)}", status_code=307)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if not _verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

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
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    token_data = response.json()
    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No id_token in response")

    claims = jose_jwt.get_unverified_claims(id_token)
    email = claims.get("email") or claims.get("preferred_username")
    display_name = claims.get("name") or email
    if not email:
        raise HTTPException(status_code=400, detail="No email in token claims")

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
        "team": team_data,
        "lobby": team_data is None and not user.is_admin,
    }


# ---------------------------------------------------------------------------
# MS365 delegated-permission connect / disconnect
# ---------------------------------------------------------------------------


@router.get("/ms365/connect")
async def ms365_connect(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Redirect user to MS365 OAuth consent for Mail.Send + ChannelMessage.Send.

    The JWT is accepted as a query parameter because this is a browser redirect
    (no Authorization header can be sent by window.location.href).
    """
    payload = verify_token(token)
    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_uuid = _uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_uuid))
    current_user = result.scalar_one_or_none()
    if current_user is None:
        raise HTTPException(status_code=401, detail="User not found")

    state = _generate_ms365_state(str(current_user.id))
    authorize_url = MICROSOFT_AUTHORIZE_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    params = {
        "client_id": settings.AZURE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.AZURE_MS365_CONNECT_REDIRECT_URI,
        "scope": _MS365_GRAPH_SCOPE,
        "response_mode": "query",
        "state": state,
        "prompt": "consent",
    }
    return RedirectResponse(url=f"{authorize_url}?{urlencode(params)}", status_code=307)


@router.get("/ms365/callback")
async def ms365_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange code for Graph tokens and persist the refresh token."""
    user_id = _verify_ms365_state(state)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    token_url = MICROSOFT_TOKEN_URL.format(tenant_id=settings.AZURE_TENANT_ID)
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(
            token_url,
            data={
                "client_id": settings.AZURE_CLIENT_ID,
                "client_secret": settings.AZURE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.AZURE_MS365_CONNECT_REDIRECT_URI,
                "scope": _MS365_GRAPH_SCOPE,
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    token_data = response.json()
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh_token in response")

    result = await db.execute(select(User).where(User.id == user_id))
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
