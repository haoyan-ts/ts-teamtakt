---
mode: agent
description: "Phase 2A: Notification engine — 8 triggers, batching, preferences, holiday calendar"
---

# Task: Notification Engine

## Context

In-app notification system with 8 triggers, user-configurable channels, batching for social events, and holiday calendar awareness.

### Notification Model

```
notifications:
  id UUID PK
  user_id FK
  trigger_type ENUM(missing_day, edit_window_closing, blocker_aging,
    team_member_blocked, social_reaction, weekly_report_ready,
    quarterly_draft_ready, team_join_request)
  title VARCHAR
  body TEXT
  data JSONB (extra context: record_date, task_id, etc.)
  is_read BOOL default false
  created_at

notification_preferences:
  id UUID PK
  user_id FK
  trigger_type ENUM (same as above)
  channel_email BOOL default (varies by trigger)
  channel_teams BOOL default (varies by trigger)
  UNIQUE(user_id, trigger_type)

holiday_calendar:
  id UUID PK
  date DATE UNIQUE
  name VARCHAR
  source ENUM(external, admin)
  is_workday BOOL default false  -- for exchanged workdays (date is normally weekend but is work)
```

### Trigger Behaviors

| Trigger | When | Repeat | Default: email | Default: Teams |
|---|---|---|---|---|
| missing_day | Next morning | Daily until reported/absent | off | on |
| edit_window_closing | Friday evening | Once/week | on | off |
| blocker_aging | Threshold crossed | Once only | off | off |
| team_member_blocked | Threshold crossed | Once only | off | on |
| social_reaction | On event | Batched (~15 min) | off | off |
| weekly_report_ready | After Sat window close | Once | on | off |
| quarterly_draft_ready | After generation | Once | on | off |
| team_join_request | On request | Once | off | on |

In-app is always on (cannot be disabled).

### Batching (social_reaction)

- On emoji/comment event: check if pending batch exists for (user, trigger=social_reaction) within last 15 min.
- If yes: increment counter in existing notification, update body ("5 people reacted to your Apr 9 record").
- If no: create new notification, start batch window.

### Holiday Calendar

- `GET /api/v1/holidays?year=` — list holidays for a year
- `POST /api/v1/holidays` — admin adds custom holiday/exchanged workday
- `DELETE /api/v1/holidays/{id}` — admin removes custom holiday
- `GET /api/v1/holidays/sync` — admin triggers sync from external API (Japanese national holidays)
- Working day check: `is_working_day(date)` → true if Mon-Fri and not in holiday_calendar (or in calendar with is_workday=true for exchanged days)

### Core Service

```python
class NotificationService:
    async def send(user_id, trigger_type, title, body, data):
        # 1. Create in-app notification (always)
        # 2. Check user preferences for this trigger
        # 3. If email enabled: queue email
        # 4. If Teams enabled: queue Teams message (Phase 3A webhook)
    
    async def send_batched(user_id, trigger_type, title_template, data):
        # Batch logic for social reactions
```

### Endpoints

- `GET /api/v1/notifications?unread_only=true` — list notifications
- `PATCH /api/v1/notifications/{id}/read` — mark as read
- `POST /api/v1/notifications/read-all` — mark all as read
- `GET /api/v1/notifications/unread-count` — for badge
- `GET /api/v1/notification-preferences` — current user's preferences
- `PUT /api/v1/notification-preferences` — update preferences

### Trigger Integration Points

Wire triggers into existing services:
- **missing_day**: daily scheduled check (or on-demand) for previous working day
- **edit_window_closing**: Friday evening check for current week
- **blocker_aging**: on daily record create/update, check carry-over age
- **team_member_blocked**: same as blocker_aging but sent to leader
- **weekly_report_ready**: after weekly report generation completes
- **quarterly_draft_ready**: after quarterly generation completes
- **team_join_request**: on join request creation
- **social_reaction**: on comment/reaction creation (Phase 3A — just wire the hook, implementation later)

## Acceptance Criteria

- [ ] Notification model with all 8 trigger types
- [ ] In-app notification CRUD (list, read, read-all, unread count)
- [ ] User preference CRUD with per-trigger channel toggles
- [ ] Batching for social_reaction trigger (15-min window)
- [ ] Holiday calendar CRUD + external sync endpoint
- [ ] `is_working_day(date)` utility using holiday calendar
- [ ] NotificationService.send() with channel routing based on preferences
- [ ] Missing day detection uses working days only
- [ ] Edit window closing notification fires Friday evening
- [ ] Alembic migration for new tables
- [ ] Seed default preferences for each trigger
- [ ] Tests: each trigger, batching, preferences, holiday calendar, working day check

## Constraints

- In-app always on — cannot be disabled.
- Batching only for social_reaction. All others: single notification per event.
- Missing day reminder: working days only (skip holidays + weekends).
- Email/Teams delivery is async (queue/background task). Don't block the API.

## Out of Scope

- MS Teams webhook integration (Phase 3A — stub the channel for now)
- Frontend notification UI (Phase 2B)
- Actual email sending for notifications (use the send infrastructure from weekly report task)
