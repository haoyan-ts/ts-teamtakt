---
mode: agent
description: "Phase 1A: User CRUD, team CRUD, join flow, roles, team transfer"
---

# Task: User & Team Management

## Context

Manage users, teams, roles, and membership. Teams are flat (one leader, N members). Each member belongs to exactly one team at a time.

### Endpoints

**Teams (admin only)**
- `POST /api/v1/teams` — create team
- `GET /api/v1/teams` — list all teams
- `DELETE /api/v1/teams/{id}` — dissolve team (blocked if members or leader remain)

**Team Membership**
- `POST /api/v1/teams/{id}/join-requests` — member requests to join (any authenticated user)
- `GET /api/v1/teams/{id}/join-requests` — list pending requests (leader/admin)
- `PATCH /api/v1/teams/{id}/join-requests/{req_id}` — approve/reject (leader/admin)
- `GET /api/v1/teams/{id}/members` — list active members (leader/admin)

**Roles (admin only)**
- `PATCH /api/v1/users/{id}/roles` — set `is_leader`, `is_admin` flags
- Admin can assign leader to a team

**User**
- `GET /api/v1/users/me` — current user profile (from auth)
- `GET /api/v1/users` — list users (admin)

### Team Transfer Logic

When a member is reassigned to a new team:
1. Set `left_at = now()` on current `team_memberships` row.
2. Create new row `(user_id, new_team_id, joined_at=now(), left_at=NULL)`.
3. Old leader retains read-only access to member's records up to `left_at`.
4. New leader sees records from `joined_at` onward.

### Orphan Prevention

- Cannot dissolve a team with active members or a leader.
- API returns 409: "Remove or reassign all members and the leader before dissolving this team."
- Cannot remove last leader from a team that still has members.

## Acceptance Criteria

- [ ] Team CRUD with cascade protection (no orphan dissolution)
- [ ] Join request flow: create → list pending → approve/reject
- [ ] Approving a join request creates team_membership and exits lobby state
- [ ] Role assignment only by admin
- [ ] Team transfer: old membership closed, new one opened, time-scoped access works
- [ ] Admin can directly assign a user to a team (bypassing join request)
- [ ] Tests: join flow, transfer, orphan prevention rejection, role assignment

## Constraints

- Roles are additive flags (booleans), not an enum.
- One active team membership per user at a time.
- Lobby users can only request to join — nothing else.

## Out of Scope

- Daily record CRUD (next task)
- Frontend UI for team management (Phase 1B)
- Sharing privilege between leaders (Phase 2A)
