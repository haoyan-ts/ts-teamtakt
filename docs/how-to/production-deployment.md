---
title: "How to Deploy ts-teamtakt to Production"
type: how-to
audience: developers
date: 2026-04-10
---

# How to Deploy ts-teamtakt to Production

This guide deploys ts-teamtakt to a production environment with a public-facing domain, covering the database, Azure Entra ID app registration, Azure OpenAI, and serving both backend and frontend.

## Prerequisites

- Local dev setup already working — see [local-dev-setup.md](./local-dev-setup.md)
- A domain name with DNS you control (e.g. `teamtakt.example.com`)
- A Linux server or container platform (e.g. Azure App Service, a VM, or Docker + a reverse proxy)
- TLS certificate for your domain (e.g. Let's Encrypt via Caddy or nginx)
- Supabase project for the database (or any hosted PostgreSQL)

---

## Steps

### 1. Add the production redirect URI to your Azure App Registration

The existing app registration (from local dev) must also allow your production callback URL.

1. Go to [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID → App registrations → your app**.
2. Go to **Authentication → Redirect URIs → Add URI**:
   ```
   https://teamtakt.example.com/api/v1/auth/callback
   ```
3. Click **Save**.

> If you want to keep local dev and production as separate Azure app registrations, repeat the full registration steps from [local-dev-setup.md](./local-dev-setup.md) using the production redirect URI instead.

---

### 2. Build the frontend

The Vite dev server is not used in production. Build static files instead:

```powershell
cd frontend
yarn install
yarn build
```

The output is in `frontend/dist/`. Serve these static files from your reverse proxy (nginx, Caddy, Azure Static Web Apps, etc.) at the root path `/`.

Configure your reverse proxy to forward `/api/*` and `/ws/*` to the FastAPI backend (e.g. `http://localhost:8000`).

---

### 3. Create the production `.env`

Create `backend/.env` on the production server. Key differences from local dev:

```env
# Database — use your Supabase (or other hosted PostgreSQL) connection string
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[password]@aws-0-xx.pooler.supabase.com:5432/postgres

# Generate a strong secret: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=replace-with-strong-random-secret

# Azure Entra ID
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-client-secret-value

# Production URLs — must match your domain exactly
AZURE_REDIRECT_URI=https://teamtakt.example.com/api/v1/auth/callback
FRONTEND_URL=https://teamtakt.example.com

ACCESS_TOKEN_EXPIRE_MINUTES=480

# First SSO login via this address is auto-promoted to admin
ADMIN_EMAIL=you@yourorg.com

# Azure OpenAI
OPENAI_API_KEY=your-azure-openai-key
OPENAI_API_BASE=https://your-resource.openai.azure.com/openai/deployments/gpt-4o
```

---

### 4. Run database migrations on the production database

On the production server (or in CI before deploying):

```powershell
cd backend
uv run alembic upgrade head
```

> Run this before starting the app. Alembic is idempotent — running it again on an already-migrated database is safe.

---

### 5. Start the backend with a production ASGI server

Do **not** use `--reload` in production. Use multiple workers:

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or with `gunicorn` + uvicorn workers (recommended for multi-process stability):

```bash
uv run gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 4
```

> `gunicorn` is not in the default dependencies. Add it with `uv add gunicorn` if you use this option.

---

### 6. Add CORS middleware for the production origin

The current codebase has no CORS middleware. In production the frontend origin differs from the backend origin, so browsers will block API calls.

Add this to `backend/app/main.py` **before** `app.include_router`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This restricts CORS to the single trusted frontend origin defined in your `.env`.

---

### 7. Configure WebSocket proxying

The social layer uses WebSockets. If you use nginx, add WebSocket upgrade headers to the `/ws` location block:

```nginx
location /ws {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

For Caddy, WebSocket proxying is automatic — no extra configuration needed.

---

## Verify

| Check                                        | Expected result                                                |
| -------------------------------------------- | -------------------------------------------------------------- |
| `https://teamtakt.example.com/api/v1/health` | `{"status": "ok"}` (or Swagger UI at `/docs`)                  |
| `https://teamtakt.example.com`               | React app loads over HTTPS                                     |
| Sign in with Microsoft                       | Redirects to Microsoft login, returns to production URL        |
| First login with `ADMIN_EMAIL`               | User promoted to admin                                         |
| Any other first login                        | User in lobby state until assigned to a team                   |
| Weekly report trigger                        | Email sent from member's own MS365 account via Microsoft Graph |
| Browser DevTools → Network                   | No CORS errors on API calls                                    |
| Browser DevTools → Network                   | WebSocket connection to `/ws` established                      |
