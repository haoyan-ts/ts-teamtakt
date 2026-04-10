---
mode: agent
description: "Phase 1B: Basic leader dashboard, controlled list management, team join approval"
---

# Task: Leader Dashboard (Basic) & Admin UI

## Context

Basic leader dashboard with 2 key views, plus management UIs for controlled lists and team join approval.

### Leader Dashboard (Basic — 2 components)

**1. Team Category Balance**
- Bar or stacked chart: per-member OKR / Routine / Interrupt distribution for the current week.
- Team-wide aggregate row at top.
- Color-coded deviation from configured targets (or default 70/30 if no targets set yet — target config UI in Phase 2B).

**2. Unreported Members**
- List of team members who haven't submitted a record for today (or selected date range).
- Shows: member name, last reported date, consecutive missing days count.
- Uses team missing-days endpoint.

### Controlled List Management UI

**Categories** (admin only):
- Table: name, sub-types (expandable), is_active toggle, sort order (drag).
- Add category button → inline form.
- Add sub-type button per category → inline form.
- Toggle is_active → confirmation "Deactivating will hide from new forms. Historical records unaffected."

**Blocker Types** (admin only):
- Simple list: name, is_active toggle, add button.

**Self-Assessment Tags** (admin only):
- List with edit name (no add/remove — fixed 4).

### Team Join Approval UI (leader)

- Notification badge on team management section.
- List: pending requests with user name, email, requested_at.
- Approve / Reject buttons per request.
- On approve: user exits lobby, gains member access.

### Routing

- `/team` — leader dashboard (restrict to users with is_leader)
- `/admin/lists` — controlled list management (restrict to is_admin)
- `/team/requests` — join approval (restrict to is_leader)

## Acceptance Criteria

- [ ] Category balance chart per member + team aggregate
- [ ] Unreported members list with missing-day data
- [ ] Category CRUD UI: add, edit name, toggle is_active, reorder, manage sub-types
- [ ] Blocker type CRUD UI
- [ ] Self-assessment tag edit UI (name only)
- [ ] Soft-delete confirmation dialog
- [ ] Team join request list with approve/reject
- [ ] Route guards: leader routes blocked for non-leaders, admin routes for non-admins
- [ ] Responsive layout

## Constraints

- Leader sees own team only.
- Controlled lists are global — admin manages for all teams.
- is_active toggle, never delete button.

## Out of Scope

- Full leader dashboard with 6 components (Phase 2B)
- Balance target configuration UI (Phase 2B)
- Metric threshold configuration (Phase 2B)
