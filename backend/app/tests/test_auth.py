from unittest.mock import AsyncMock, MagicMock

from jose import jwt as jose_jwt

from app.api.v1.auth import _generate_state


def make_fake_id_token(email: str, name: str) -> str:
    """Create a minimal JWT with email/name claims (no real signature verification)."""
    return jose_jwt.encode(
        {"email": email, "name": name, "sub": "ms-oid-stub"},
        "any-key",
        algorithm="HS256",
    )


def make_mock_httpx_cm(id_token: str):
    """Return a mock async context manager simulating httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id_token": id_token,
        "access_token": "ms-fake-access-token",
        "token_type": "Bearer",
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


# ---------------------------------------------------------------------------
# 1. GET /login → 307 redirect to Microsoft
# ---------------------------------------------------------------------------
async def test_login_redirect(client):
    resp = await client.get("/api/v1/auth/login")
    assert resp.status_code == 307
    assert "login.microsoftonline.com" in resp.headers["location"]


# ---------------------------------------------------------------------------
# 2. GET /me without token → 401
# ---------------------------------------------------------------------------
async def test_me_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Callback: new user created, JWT returned, lobby=true
# ---------------------------------------------------------------------------
async def test_callback_new_user(client, mocker):
    state = _generate_state()
    id_token = make_fake_id_token("newuser@example.com", "New User")
    mocker.patch(
        "app.api.v1.auth.httpx.AsyncClient", return_value=make_mock_httpx_cm(id_token)
    )

    resp = await client.get(f"/api/v1/auth/callback?code=test-code&state={state}")
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "token=" in location

    token = location.split("token=")[1]
    resp2 = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["email"] == "newuser@example.com"
    assert data["lobby"] is True
    assert data["team"] is None


# ---------------------------------------------------------------------------
# 4. Callback: existing user returned, JWT works
# ---------------------------------------------------------------------------
async def test_callback_existing_user(client, mocker):
    # "newuser@example.com" was already created in test_callback_new_user (session-scoped DB)
    state = _generate_state()
    id_token = make_fake_id_token("newuser@example.com", "New User")
    mocker.patch(
        "app.api.v1.auth.httpx.AsyncClient", return_value=make_mock_httpx_cm(id_token)
    )

    resp = await client.get(f"/api/v1/auth/callback?code=test-code&state={state}")
    assert resp.status_code == 307
    token = resp.headers["location"].split("token=")[1]

    resp2 = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp2.status_code == 200
    assert resp2.json()["email"] == "newuser@example.com"


# ---------------------------------------------------------------------------
# 5. GET /me with valid JWT → 200, correct user info
# ---------------------------------------------------------------------------
async def test_me_with_valid_token(client, mocker):
    state = _generate_state()
    id_token = make_fake_id_token("metest@example.com", "Me Test")
    mocker.patch(
        "app.api.v1.auth.httpx.AsyncClient", return_value=make_mock_httpx_cm(id_token)
    )

    resp = await client.get(f"/api/v1/auth/callback?code=test-code&state={state}")
    token = resp.headers["location"].split("token=")[1]

    resp2 = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["email"] == "metest@example.com"
    assert data["display_name"] == "Me Test"
    assert data["is_leader"] is False
    assert data["is_admin"] is False
    assert data["preferred_locale"] == "en"
    assert data["team"] is None
    assert data["lobby"] is True


# ---------------------------------------------------------------------------
# 6. ADMIN_EMAIL bootstrap: first login with matching email → is_admin=True
# ---------------------------------------------------------------------------
async def test_admin_email_bootstrap(client, mocker):
    from app.config import settings

    original_admin = settings.ADMIN_EMAIL
    settings.ADMIN_EMAIL = "bootstrap-admin@example.com"
    try:
        state = _generate_state()
        id_token = make_fake_id_token("bootstrap-admin@example.com", "Bootstrap Admin")
        mocker.patch(
            "app.api.v1.auth.httpx.AsyncClient",
            return_value=make_mock_httpx_cm(id_token),
        )

        resp = await client.get(f"/api/v1/auth/callback?code=test-code&state={state}")
        assert resp.status_code == 307
        token = resp.headers["location"].split("token=")[1]

        resp2 = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp2.status_code == 200
        assert resp2.json()["is_admin"] is True
    finally:
        settings.ADMIN_EMAIL = original_admin


# ---------------------------------------------------------------------------
# 7. Lobby user can still access /health
# ---------------------------------------------------------------------------
async def test_health_accessible_for_lobby_user(client, mocker):
    state = _generate_state()
    id_token = make_fake_id_token("lobbytest@example.com", "Lobby Test")
    mocker.patch(
        "app.api.v1.auth.httpx.AsyncClient", return_value=make_mock_httpx_cm(id_token)
    )

    resp = await client.get(f"/api/v1/auth/callback?code=test-code&state={state}")
    assert resp.status_code == 307

    # Health endpoint is public — no auth required
    resp2 = await client.get("/api/v1/health")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# 8. POST /logout → 200
# ---------------------------------------------------------------------------
async def test_logout(client):
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Logged out"}
