---
mode: agent
description: "Phase 1A: Microsoft 365 SSO authentication via OIDC"
---

# Task: MS365 SSO Authentication

## Context

Implement authentication using Microsoft 365 / Azure AD (Entra ID) SSO via OIDC. Every employee has a company email account. No separate password management.

### Auth Flow

1. Frontend redirects to Microsoft login.
2. Microsoft returns authorization code to backend callback.
3. Backend exchanges code for tokens, extracts user info (email, display_name).
4. If email not in `users` table → create new user (lobby state: no team, cannot use features).
5. Issue session token (JWT or session cookie) for subsequent API calls.

### Dependencies

- `users` table from schema task
- `team_memberships` table (to check if user is assigned to a team)

### Endpoints

- `GET /api/v1/auth/login` — redirect to Microsoft OIDC authorize URL
- `GET /api/v1/auth/callback` — handle OIDC callback, create/find user, issue token
- `POST /api/v1/auth/logout` — invalidate session
- `GET /api/v1/auth/me` — return current user info (roles, team, lobby status)

### Lobby State

First SSO login creates a user with `is_leader=false, is_admin=false`, no active team_membership. The `/me` endpoint returns `{ ..., team: null, lobby: true }`. Middleware blocks access to all non-auth endpoints for lobby users.

## Acceptance Criteria

- [ ] OIDC flow works with Azure AD / Entra ID (configurable tenant, client_id, client_secret)
- [ ] First-time login creates unassigned user automatically
- [ ] `/me` returns correct user info, roles, team, and lobby flag
- [ ] Lobby users get 403 on all non-auth endpoints
- [ ] Token refresh or re-auth works when session expires
- [ ] Admin bootstrap: env var `ADMIN_EMAIL` — if set, first login with that email gets `is_admin=true`
- [ ] Tests with mocked OIDC provider

## Constraints

- No password storage. SSO only.
- Lobby state users cannot submit records, access dashboards, or use social features.
- Session token must include `user_id` and role flags for fast middleware checks.

## Out of Scope

- User/team management API (next task)
- Frontend login UI (Phase 1B)
- MS Teams integration
