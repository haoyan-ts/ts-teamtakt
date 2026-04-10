---
mode: agent
description: "Phase 1A: DailyRecord + TaskEntry CRUD, carry-over, edit window, unlock"
---

# Task: Daily Record CRUD

## Context

Core daily reporting: members submit daily records with task entries. Includes carry-over pre-fill, edit window enforcement, and leader unlock.

### Endpoints

- `POST /api/v1/daily-records` — create record for a date
- `GET /api/v1/daily-records?user_id=&date=` — get record(s)
- `PUT /api/v1/daily-records/{id}` — update record (within edit window or unlocked)
- `GET /api/v1/daily-records/carry-over` — get running/blocked tasks from most recent record for pre-fill
- `POST /api/v1/unlock-grants` — leader grants unlock on (user_id, record_date)
- `DELETE /api/v1/unlock-grants/{id}` — leader revokes unlock

### DailyRecord Fields

`user_id, record_date (DATE), day_load (1-5), day_note (text), form_opened_at (timestamptz)`

### TaskEntry Fields (nested under DailyRecord)

`category_id, sub_type_id?, project_id, task_description, effort (1-5), status (todo|running|done|blocked), blocker_type_id?, blocker_text?, carried_from_id? (immutable), sort_order`

Plus `self_assessment_tags[]` with exactly one `is_primary=true`.

### Edit Window Logic (server-side)

```python
record_week_start = monday_of(record_date)
edit_deadline = record_week_start + timedelta(days=12)  # Saturday 00:00 JST

# Check at submit time:
now_jst = now_in_jst()
if now_jst < edit_deadline:
    allow()
elif form_opened_at < edit_deadline and now_jst < edit_deadline + timedelta(minutes=15):
    allow()  # grace period
elif has_active_unlock(user_id, record_date):
    allow()
else:
    reject("Edit window closed. Contact your leader for an unlock.")
```

- `form_opened_at` must be within last 6 hours (reject stale tokens).
- No `locked` column — always computed.

### Carry-over Logic

- `GET /carry-over`: find most recent daily_record for user, return task_entries with status=running or blocked.
- On POST: client sends `carried_from_id` for pre-filled tasks. Server validates the FK exists and belongs to the same user.
- `carried_from_id` is immutable — reject updates that try to change it.

### Mutual Exclusion with Absence

On create: check `absences` table for `(user_id, record_date)`. If exists, reject with: "An absence is already recorded for this date. Remove it first."

### Self-Assessment Tag Validation

On save: for each task_entry, count tags with `is_primary=true`. Must be exactly 1. If 0 or >1, reject with error listing the offending task.

### Unlock Grant

- `unlock_grants(user_id, record_date, granted_by, granted_at, revoked_at)`
- Targets (user_id, record_date), not a record row.
- At most one active unlock per (user, date): `UNIQUE(user_id, record_date) WHERE revoked_at IS NULL`.
- Leader can only unlock for own team members. Admin can unlock anyone.

## Acceptance Criteria

- [ ] Create/read/update daily record with nested task entries
- [ ] Edit window enforced server-side with correct formula
- [ ] 15-min grace period works when form_opened_at is valid
- [ ] Stale form_opened_at (>6h) rejected
- [ ] Carry-over endpoint returns running/blocked tasks
- [ ] carried_from_id immutable after creation
- [ ] Mutual exclusion with absence checked on create/update
- [ ] Self-assessment tag primary validation on every save
- [ ] Unlock grant CRUD, scoped to leader's team
- [ ] Audit trail: edits to post-window records logged (who, when, what)
- [ ] Tests: window open, window closed, grace period, unlock, carry-over, mutual exclusion, tag validation

## Constraints

- All date/time in JST. No per-user timezone.
- carried_from_id immutable — reject any PUT that changes it.
- No approval workflow. Submitted data trusted as-is.

## Out of Scope

- Controlled list CRUD (next task — assume seed data exists)
- Visibility filtering of private fields (task 06)
- Frontend form (Phase 1B)
