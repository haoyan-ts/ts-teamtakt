import hashlib
import hmac
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from jose import jwt as jose_jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.engine import get_db
from app.db.models.team import Team, TeamMembership
from app.db.models.user import User

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
        url=f"{settings.FRONTEND_URL}/?token={access_token}", status_code=307
    )


@router.post("/logout")
async def logout():
    return {"message": "Logged out"}


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
        "lobby": team_data is None,
    }
