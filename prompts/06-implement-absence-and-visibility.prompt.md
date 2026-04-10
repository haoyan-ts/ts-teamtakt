---
mode: agent
description: "Phase 1A: Absence CRUD, missing day detection, field-level visibility"
---

# Task: Absence Tracking & Visibility

## Context

Complete absence management and field-level visibility filtering across all record endpoints.

### Absence Endpoints

- `POST /api/v1/absences` — create absence for a date
- `GET /api/v1/absences?user_id=&start_date=&end_date=` — list absences
- `PUT /api/v1/absences/{id}` — update (within edit window)
- `DELETE /api/v1/absences/{id}` — remove (within edit window, allows user to then submit a daily record)

Types: `holiday, exchanged_holiday, illness, other`

### Mutual Exclusion

On create/update: check `daily_records` for `(user_id, record_date)`. If exists, reject: "A daily record exists for this date. Remove it first to mark an absence."

Same edit window and lock formula as daily records. Absence records are also locked after window closes.

### Missing Day Detection

- `GET /api/v1/missing-days?user_id=&start_date=&end_date=` — returns dates where neither daily_record nor absence exists (working days only, using holiday calendar).
- For leader: `GET /api/v1/teams/{id}/missing-days?week=` — team-wide unreported days.
- Working days: Mon-Fri minus holidays from holiday calendar (in this phase, use a simple weekend filter; holiday calendar integration in Phase 2A).

### Visibility Filtering

Apply to ALL record read endpoints (daily-records, team views, etc.):

**Public fields** (visible to all authenticated users):
- task_description, project, category, sub_type, effort, status, self_assessment_tags, day_note, blocker_type

**Private fields** (visible only to: record owner, owner's leader, admin):
- day_load, blocker_text

Implementation:
- Single shared filtering function that takes `record, requester` and strips private fields if requester lacks permission.
- Requester role check: is requester the owner? Is requester leader of owner's current team? Is requester admin?
- For time-scoped team transfers: check if requester was leader during the record's date range via team_memberships.
- This SAME function must be reusable by WebSocket payloads later (do not couple to HTTP request).

## Acceptance Criteria

- [ ] Absence CRUD with type enum
- [ ] Mutual exclusion with daily_records enforced both ways
- [ ] Absence respects same edit window formula as daily records
- [ ] Missing day endpoint returns unreported working days
- [ ] Team-wide missing days for leader
- [ ] Visibility filter strips private fields for unauthorized requesters
- [ ] Visibility works for: owner (all fields), leader (all for own team), other members (public only), admin (all)
- [ ] Time-scoped visibility: old leader sees full fields only for records within their tenure
- [ ] Filtering function is decoupled from HTTP (reusable for WS)
- [ ] Tests: mutual exclusion both directions, visibility per role, time-scoped leader access, missing day calculation

## Constraints

- All dates in JST. Weekend filter for missing days (holiday calendar deferred).
- Same edit window formula for absences. Same unlock_grant table works (targets user+date).
- Do not duplicate visibility logic — single function, reused everywhere.

## Out of Scope

- Holiday calendar integration (Phase 2A)
- Notification triggers for missing days (Phase 2A)
- Frontend (Phase 1B)
