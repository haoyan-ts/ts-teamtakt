"""Tests for GitHub OAuth account linking — issue #21."""

from __future__ import annotations

import secrets
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import oauth_state
from app.core.security import create_access_token
from app.core.token_encryption import decrypt_token, encrypt_token
from app.db.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_ENC_KEY = secrets.token_hex(32)  # 64-char hex — valid 32-byte key


def _make_user(db_session, email: str = "gh_user@example.com") -> User:
    user = User(email=email, display_name="GH User")
    db_session.add(user)
    return user


def _make_token(user: User) -> str:
    return create_access_token(
        {"sub": str(user.id), "is_leader": user.is_leader, "is_admin": user.is_admin}
    )


def _make_httpx_mock(
    *,
    token_status: int = 200,
    token_json: dict | None = None,
    user_status: int = 200,
    user_json: dict | None = None,
) -> MagicMock:
    """Build a mock httpx.AsyncClient that returns canned responses for two calls."""
    if token_json is None:
        token_json = {"access_token": "ghp_fake_token_123"}
    if user_json is None:
        user_json = {"login": "octocat"}

    token_resp = MagicMock()
    token_resp.status_code = token_status
    token_resp.json.return_value = token_json

    user_resp = MagicMock()
    user_resp.status_code = user_status
    user_resp.json.return_value = user_json

    mock_client = AsyncMock()
    # post() → token exchange; get() → GitHub user info
    mock_client.post = AsyncMock(return_value=token_resp)
    mock_client.get = AsyncMock(return_value=user_resp)
    mock_client.delete = AsyncMock(return_value=MagicMock(status_code=204))

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


# ---------------------------------------------------------------------------
# 1. GET /auth/github/authorize — returns redirect to GitHub
# ---------------------------------------------------------------------------
async def test_github_authorize_redirects(client, db_session, mocker):
    """Authorize endpoint returns a JSON URL pointing to GitHub with state and PKCE params."""
    user = _make_user(db_session, "auth_redirect@example.com")
    await db_session.commit()
    await db_session.refresh(user)
    token = _make_token(user)

    mocker.patch("app.api.v1.auth.settings.GITHUB_CLIENT_ID", "test-client-id")

    resp = await client.get(
        "/api/v1/auth/github/authorize",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    location = data["url"]
    assert "github.com/login/oauth/authorize" in location
    assert "state=" in location
    assert "scope=repo+read%3Auser" in location or "scope=repo" in location


# ---------------------------------------------------------------------------
# 2. GET /auth/github/authorize — 503 when not configured
# ---------------------------------------------------------------------------
async def test_github_authorize_not_configured(client, db_session, mocker):
    user = _make_user(db_session, "notconf@example.com")
    await db_session.commit()
    await db_session.refresh(user)
    token = _make_token(user)

    mocker.patch("app.api.v1.auth.settings.GITHUB_CLIENT_ID", None)

    resp = await client.get(
        "/api/v1/auth/github/authorize",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 3. GET /auth/github/callback — stores encrypted token, linked in /users/me
# ---------------------------------------------------------------------------
async def test_github_callback_stores_token(client, db_session, mocker):
    """Successful callback stores encrypted token and github_login on user."""
    user = _make_user(db_session, "callback_store@example.com")
    await db_session.commit()
    await db_session.refresh(user)

    # Pre-seed a GitHub state entry
    state = secrets.token_urlsafe(32)
    oauth_state.store_github_state(state, user_id=str(user.id))

    mocker.patch("app.api.v1.auth.settings.GITHUB_CLIENT_ID", "test-id")
    mocker.patch("app.api.v1.auth.settings.GITHUB_CLIENT_SECRET", "test-secret")
    mocker.patch("app.api.v1.auth.settings.GITHUB_TOKEN_ENCRYPTION_KEY", _TEST_ENC_KEY)
    mocker.patch(
        "app.api.v1.auth.httpx.AsyncClient",
        return_value=_make_httpx_mock(),
    )

    resp = await client.get(
        f"/api/v1/auth/github/callback?code=gh-code&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "github=connected" in resp.headers["location"]

    await db_session.refresh(user)
    assert user.github_access_token_enc is not None
    assert user.github_token_iv is not None
    assert user.github_login == "octocat"

    # Verify the stored token decrypts correctly
    decrypted = decrypt_token(
        user.github_access_token_enc, user.github_token_iv, _TEST_ENC_KEY
    )
    assert decrypted == "ghp_fake_token_123"

    # /users/me should reflect linked state — use app token for user
    app_token = _make_token(user)
    me_resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {app_token}"}
    )
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["github_linked"] is True
    assert data["github_login"] == "octocat"


# ---------------------------------------------------------------------------
# 4. GET /auth/github/callback — invalid/expired state → 400
# ---------------------------------------------------------------------------
async def test_github_callback_invalid_state(client):
    resp = await client.get(
        "/api/v1/auth/github/callback?code=any&state=definitely-invalid-state"
    )
    assert resp.status_code == 400
    assert "state" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. DELETE /auth/github/unlink — clears token
# ---------------------------------------------------------------------------
async def test_github_unlink_clears_token(client, db_session, mocker):
    user = _make_user(db_session, "unlink_test@example.com")
    token_enc, token_iv = encrypt_token("ghp_fake", _TEST_ENC_KEY)
    user.github_access_token_enc = token_enc
    user.github_token_iv = token_iv
    user.github_login = "octocat"
    await db_session.commit()
    await db_session.refresh(user)

    mocker.patch("app.api.v1.auth.settings.GITHUB_CLIENT_ID", "test-id")
    mocker.patch("app.api.v1.auth.settings.GITHUB_CLIENT_SECRET", "test-secret")
    mocker.patch("app.api.v1.auth.settings.GITHUB_TOKEN_ENCRYPTION_KEY", _TEST_ENC_KEY)
    mocker.patch(
        "app.api.v1.auth.httpx.AsyncClient",
        return_value=_make_httpx_mock(),
    )

    app_token = _make_token(user)
    resp = await client.delete(
        "/api/v1/auth/github/unlink",
        headers={"Authorization": f"Bearer {app_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["github_linked"] is False

    await db_session.refresh(user)
    assert user.github_access_token_enc is None
    assert user.github_token_iv is None
    assert user.github_login is None


# ---------------------------------------------------------------------------
# 6. github_autofill uses per-user token when available
# ---------------------------------------------------------------------------
async def test_autofill_uses_user_token(db_session, mocker):
    """resolve_github_token returns the user's decrypted token."""
    from app.services.github_autofill import resolve_github_token

    user = User(email="autofill_user@example.com", display_name="AF User")
    token_enc, token_iv = encrypt_token("ghp_user_token", _TEST_ENC_KEY)
    user.github_access_token_enc = token_enc
    user.github_token_iv = token_iv

    mocker.patch(
        "app.services.github_autofill.settings.GITHUB_TOKEN_ENCRYPTION_KEY",
        _TEST_ENC_KEY,
    )

    resolved = await resolve_github_token(user)
    assert resolved == "ghp_user_token"


# ---------------------------------------------------------------------------
# 7. github_autofill falls back to shared GITHUB_TOKEN
# ---------------------------------------------------------------------------
async def test_autofill_falls_back_to_shared_token(mocker):
    from app.services.github_autofill import resolve_github_token

    user = User(email="fallback@example.com", display_name="FB User")
    # No linked token
    mocker.patch("app.services.github_autofill.settings.GITHUB_TOKEN", "shared-token")

    resolved = await resolve_github_token(user)
    assert resolved == "shared-token"


# ---------------------------------------------------------------------------
# 8. fetch_github_issue: 401 from GitHub clears token, raises GitHubTokenRevokedError
# ---------------------------------------------------------------------------
async def test_revoked_token_cleared_on_401(db_session, mocker):
    from app.services.github_autofill import GitHubTokenRevokedError, fetch_github_issue

    user = User(email="revoked@example.com", display_name="Revoked")
    token_enc, token_iv = encrypt_token("ghp_revoked", _TEST_ENC_KEY)
    user.github_access_token_enc = token_enc
    user.github_token_iv = token_iv
    user.github_login = "octocat"
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mocker.patch("app.services.github_autofill.httpx.AsyncClient", return_value=mock_cm)
    mocker.patch(
        "app.services.github_autofill.settings.GITHUB_TOKEN_ENCRYPTION_KEY",
        _TEST_ENC_KEY,
    )

    with pytest.raises(GitHubTokenRevokedError):
        await fetch_github_issue(
            "https://github.com/owner/repo/issues/1",
            user=user,
            db=db_session,
        )

    await db_session.refresh(user)
    assert user.github_access_token_enc is None
    assert user.github_token_iv is None
    assert user.github_login is None


# ---------------------------------------------------------------------------
# 9. Raw token never returned in /users/me or /auth/me
# ---------------------------------------------------------------------------
async def test_raw_token_never_in_response(client, db_session):
    user = _make_user(db_session, "notoken_leak@example.com")
    token_enc, token_iv = encrypt_token("ghp_secret_token", _TEST_ENC_KEY)
    user.github_access_token_enc = token_enc
    user.github_token_iv = token_iv
    user.github_login = "octocat"
    await db_session.commit()
    await db_session.refresh(user)

    app_token = _make_token(user)
    headers = {"Authorization": f"Bearer {app_token}"}

    for path in ["/api/v1/users/me", "/api/v1/auth/me"]:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200
        body = resp.text
        assert "ghp_secret_token" not in body
        assert token_enc not in body
        assert token_iv not in body
