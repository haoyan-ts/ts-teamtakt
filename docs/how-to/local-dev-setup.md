---
title: "How to Set Up the Local Development Environment"
type: how-to
audience: developers
date: 2026-04-10
---

# How to Set Up the Local Development Environment

This guide gets ts-teamtakt running on your local machine, covering the database, MS365 SSO, and the optional Azure OpenAI integration. All URLs point to `localhost`.

## Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) installed
- Node.js 20+ and `yarn` installed
- A [Supabase](https://supabase.com) account (free tier is enough — used as a hosted PostgreSQL only)
- An Azure account with access to a Microsoft 365 tenant (for SSO)
- _(Optional)_ Access to Azure OpenAI (for AI-drafted emails and quarterly reports)

---

## Steps

### 1. Get a PostgreSQL connection string from Supabase

Supabase is used **only as a hosted PostgreSQL database**. You do not need the Supabase JS client, Auth, or Realtime features.

1. In your Supabase project, go to **Project Settings → Database → Connection string → URI**.
2. Copy the URI. It looks like:
   ```
   postgresql://postgres.[ref]:[password]@aws-0-xx.pooler.supabase.com:5432/postgres
   ```
3. Change the scheme from `postgresql://` to `postgresql+asyncpg://` — SQLAlchemy requires the async driver prefix:
   ```
   postgresql+asyncpg://postgres.[ref]:[password]@aws-0-xx.pooler.supabase.com:5432/postgres
   ```

Keep this value — it becomes `DATABASE_URL` in your `.env`.

---

### 2. Register an Azure App for MS365 SSO

1. Go to [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID → App registrations → New registration**.
2. Fill in:
   - **Name**: `ts-teamtakt-local` (or any name)
   - **Supported account types**: "Accounts in this organizational directory only"
   - **Redirect URI**: Platform = **Web**, Value = `http://localhost:8000/api/v1/auth/callback`
3. Click **Register**.
4. From the app's **Overview** page, copy:
   - **Application (client) ID** → this is `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → this is `AZURE_TENANT_ID`
5. Go to **Certificates & secrets → New client secret**, set an expiry, and click **Add**. Copy the **Value** immediately (it is only shown once) → this is `AZURE_CLIENT_SECRET`.

---

### 3. Grant Microsoft Graph delegated permissions

The app uses MS Graph to authenticate users and to send emails from each user's own MS365 account.

1. In your app registration, go to **API permissions → Add a permission → Microsoft Graph → Delegated permissions**.
2. Add all of the following:
   - `openid`
   - `profile`
   - `email`
   - `Mail.Send`
   - `offline_access`
3. Click **Grant admin consent for [your tenant]** and confirm.

---

### 4. Set up Azure OpenAI _(optional)_

The app returns a placeholder draft when no API key is configured, so you can skip this step and everything else will still work.

If you want real AI generation:

1. In the [Azure Portal](https://portal.azure.com), create an **Azure OpenAI** resource in your preferred region.
2. Open the resource → **Model deployments → Manage deployments** (opens Azure AI Studio).
3. Click **New deployment**, select model **`gpt-4o`**, and set the deployment name to **`gpt-4o`** (the code references this exact name).
4. From the resource's **Keys and Endpoint** page, copy:
   - **Endpoint** (e.g. `https://your-resource.openai.azure.com/`)
   - **KEY 1**
5. Construct `OPENAI_API_BASE` as:
   ```
   https://your-resource.openai.azure.com/openai/deployments/gpt-4o
   ```

---

### 5. Create `backend/.env`

Create the file `backend/.env` (next to `pyproject.toml`). Use the values collected in the steps above:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[password]@aws-0-xx.pooler.supabase.com:5432/postgres

# App secret — generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=replace-with-generated-secret

# Azure Entra ID (MS365 SSO)
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-client-secret-value
AZURE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback

# Frontend origin
FRONTEND_URL=http://localhost:5173

# Session length (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=480

# First login via this email address is automatically promoted to admin
ADMIN_EMAIL=you@yourorg.com

# Azure OpenAI (optional — omit both lines to use placeholder drafts)
OPENAI_API_KEY=your-azure-openai-key
OPENAI_API_BASE=https://your-resource.openai.azure.com/openai/deployments/gpt-4o
```

Generate a strong `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### 6. Install dependencies and initialise the database

```powershell
cd backend
uv sync --dev
```

**First run only — generate the initial migration:**

The `alembic/versions/` directory ships empty. On a fresh clone you must generate the migration file before you can apply it:

```powershell
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

> **What this does**
>
> - `alembic revision --autogenerate` diffs your SQLAlchemy models against the (empty) database and produces a migration script in `alembic/versions/`.
> - `alembic upgrade head` executes that script and creates all tables in the database.

**Subsequent runs (after pulling new changes):**

If a teammate has added new migrations, just apply them — no need to autogenerate again:

```powershell
uv run alembic upgrade head
```

**Seed data**

When the backend starts for the first time, the `lifespan` handler in `app/main.py` automatically inserts seed data (self-assessment tags, default categories, and the `output_language` admin setting). No manual step is needed — simply starting the server is enough.

---

### 7. Start the backend and frontend

Open two terminals:

**Terminal 1 — backend:**

```powershell
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend:**

```powershell
cd frontend
yarn install
yarn dev
```

---

## Verify

| Check                                  | Expected result                                                            |
| -------------------------------------- | -------------------------------------------------------------------------- |
| `http://localhost:8000/docs`           | FastAPI Swagger UI loads                                                   |
| `http://localhost:5173`                | React app loads                                                            |
| Click **Sign in with Microsoft**       | Redirects to `login.microsoftonline.com`, completes, returns to app        |
| First login with `ADMIN_EMAIL`         | User has `is_admin=true` in the database                                   |
| First login with any other account     | User lands in lobby state (cannot submit records until assigned to a team) |
| Weekly email trigger (with OpenAI set) | Draft generated via Azure OpenAI                                           |
| Weekly email trigger (without OpenAI)  | Log shows `OPENAI_API_KEY not set; returning placeholder`                  |
| Run tests (no `.env` needed)           | `cd backend && uv run pytest` — all tests pass using in-memory SQLite      |
