---
mode: agent
description: "Phase 1A: PostgreSQL schema design and FastAPI project scaffolding"
---

# Task: Schema & FastAPI Setup

## Context

Set up the `backend/` directory with a FastAPI project and define the full PostgreSQL schema.

### Tech Stack

- Python FastAPI with **uv** for dependency management
- PostgreSQL with async driver (asyncpg via SQLAlchemy async)
- Alembic for migrations
- pytest for testing

### Project Structure

```
backend/
  pyproject.toml
  alembic.ini
  alembic/
    versions/
  app/
    main.py
    config.py
    db/
      engine.py
      models/
      schemas/
    api/
      v1/
    core/
      security.py
    tests/
```

### Schema — All Tables

**users**: `id (UUID PK), email (UNIQUE), display_name, is_leader (bool, default false), is_admin (bool, default false), preferred_locale (varchar, default 'en'), created_at`

**teams**: `id (UUID PK), name, created_at`

**team_memberships**: `id (UUID PK), user_id FK, team_id FK, joined_at (timestamptz), left_at (timestamptz, nullable)`
- Active membership: `left_at IS NULL`. One active membership per user.

**daily_records**: `id (UUID PK), user_id FK, record_date (DATE), day_load (int 1-5), day_note (text), form_opened_at (timestamptz), created_at, updated_at`
- `UNIQUE(user_id, record_date)`

**task_entries**: `id (UUID PK), daily_record_id FK, category_id FK, sub_type_id FK (nullable), project_id FK, task_description (text), effort (int 1-5), status ENUM(todo, running, done, blocked), blocker_type_id FK (nullable), blocker_text (text, nullable), carried_from_id FK self-ref (nullable), sort_order (int)`

**task_entry_self_assessment_tags**: `id (UUID PK), task_entry_id FK, self_assessment_tag_id FK, is_primary (bool)`
- UNIQUE(task_entry_id, self_assessment_tag_id)

**absences**: `id (UUID PK), user_id FK, record_date (DATE), absence_type ENUM(holiday, exchanged_holiday, illness, other), note (text, nullable), created_at`
- `UNIQUE(user_id, record_date)`

**unlock_grants**: `id (UUID PK), user_id FK, record_date (DATE), granted_by FK, granted_at (timestamptz), revoked_at (timestamptz, nullable)`
- Partial unique: `UNIQUE(user_id, record_date) WHERE revoked_at IS NULL`

**categories**: `id (UUID PK), name, is_active (bool, default true), sort_order`

**category_sub_types**: `id (UUID PK), category_id FK, name, is_active (bool, default true), sort_order`

**self_assessment_tags**: `id (UUID PK), name, is_active (bool, default true)`

**blocker_types**: `id (UUID PK), name, is_active (bool, default true)`

**projects**: `id (UUID PK), name, scope ENUM(personal, team, cross_team), team_id FK (nullable, NULL for cross_team), created_by FK, is_active (bool, default true), created_at`

**sharing_grants**: `id (UUID PK), granting_leader_id FK, granted_to_leader_id FK, team_id FK, granted_at (timestamptz), revoked_at (timestamptz, nullable)`

**team_join_requests**: `id (UUID PK), user_id FK, team_id FK, status ENUM(pending, approved, rejected), requested_at, resolved_at, resolved_by FK (nullable)`

**team_extra_ccs**: `id (UUID PK), team_id FK, email (varchar)`

## Acceptance Criteria

- [ ] `uv init` project with pyproject.toml, all dependencies declared
- [ ] All tables above created as SQLAlchemy ORM models
- [ ] Alembic initial migration generates all tables
- [ ] `alembic upgrade head` runs clean against a fresh database
- [ ] FastAPI app starts with health endpoint at `/api/v1/health`
- [ ] OpenAPI docs auto-served at `/docs`
- [ ] pytest fixture creates test DB, runs migrations, tears down
- [ ] `.env.example` with all required env vars documented

## Constraints

- All dates as DATE type. Single timezone JST — no per-user offset.
- No `locked` column on daily_records.
- `carried_from_id` nullable but immutable after creation (enforce in app layer, not schema).
- Controlled lists use `is_active` for soft-delete. No CASCADE DELETE on any controlled list FK.
- Roles: `is_leader` and `is_admin` are independent booleans, not an enum.

## Out of Scope

- API endpoints beyond health check (next tasks)
- Authentication (next task)
- Frontend
