---
mode: agent
description: "Phase 1A: Categories, sub-types, blocker types, tags, project namespace"
---

# Task: Controlled Lists & Projects

## Context

Admin-managed global lists and 3-scope project namespace. All controlled lists use soft-delete.

### Categories (admin-managed)

Two-level hierarchy: category → optional sub-types.

- `POST /api/v1/categories` — create category (admin)
- `GET /api/v1/categories` — list active categories (+ sub-types nested). For form dropdowns.
- `GET /api/v1/categories?include_inactive=true` — include deactivated (admin)
- `PATCH /api/v1/categories/{id}` — update name, sort_order, is_active
- `POST /api/v1/categories/{id}/sub-types` — add sub-type
- `PATCH /api/v1/category-sub-types/{id}` — update sub-type

Soft-delete: set `is_active=false`. Historical records keep FK. Deactivated items hidden from new-entry forms, shown on old records. Reactivation allowed.

### Self-Assessment Tags (admin-managed)

Fixed 4: OKR, Routine, Team Contribution, Company Contribution.

- `GET /api/v1/self-assessment-tags` — list active
- `PATCH /api/v1/self-assessment-tags/{id}` — update (admin)

### Blocker Types (admin-managed)

Flat list, soft-delete.

- `POST /api/v1/blocker-types` — create (admin)
- `GET /api/v1/blocker-types` — list active
- `PATCH /api/v1/blocker-types/{id}` — update, soft-delete (admin)

### Projects

Three scopes: personal, team, cross_team.

- `POST /api/v1/projects` — create. Scope determined by request:
  - Member: personal or team (team_id = member's team)
  - Leader: can also create cross_team (team_id = NULL)
- `GET /api/v1/projects` — list projects visible to requester:
  - Own personal + own team + all cross_team
- `PATCH /api/v1/projects/{id}` — update name, is_active
- `POST /api/v1/projects/{id}/promote` — leader promotes team→cross_team:
  - Set `scope=cross_team, team_id=NULL`
  - Send in-app notification to `created_by` user (no veto)
  - Only leader of the project's team (or admin) can promote

## Acceptance Criteria

- [ ] Category CRUD with nested sub-types
- [ ] Soft-delete (is_active) on categories, sub-types, blocker types
- [ ] GET endpoints filter by is_active by default, include_inactive flag for admin
- [ ] Historical records display deactivated items correctly (FK intact)
- [ ] Self-assessment tags: list + update
- [ ] Blocker types: CRUD + soft-delete
- [ ] Projects: create with scope validation (member can't create cross_team)
- [ ] Project listing filtered by visibility (personal: owner only, team: team members, cross_team: all)
- [ ] Promote endpoint: scope change + notification + permission check
- [ ] Seed data: initial categories (OKR, Routine, Interrupt), 4 self-assessment tags
- [ ] Tests: soft-delete, scope enforcement, promotion, seed data

## Constraints

- Never hard-delete controlled list items. Always soft-delete.
- Balance targets are at top-level category only (not sub-type).
- Promotion: no veto, but creator gets notification.
- Categories/tags/blocker types are global (not per-team).

## Out of Scope

- Balance target configuration (Phase 2A)
- Frontend for list management (Phase 1B)
