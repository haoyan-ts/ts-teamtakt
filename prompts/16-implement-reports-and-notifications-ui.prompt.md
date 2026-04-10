---
mode: agent
description: "Phase 2B: Weekly report review, email editor, monthly view, notifications, export, unlock UI"
---

# Task: Reports, Notifications & Export UI

## Context

Frontend for weekly report review, email draft editing, monthly aggregation, notification bell, export downloads, and leader unlock. Consolidates remaining Phase 2B frontend work.

### Weekly Report Review (`/reports/weekly/:week_start?`)

- Week selector (defaults to most recent completed week).
- Dashboard view: 6 metrics from the weekly report (days reported, category breakdown, top projects, carry-over, blockers, tag distribution).
- Charts reuse components from member dashboard where applicable.
- Download button → CSV/XLSX export of the week's data.

### Weekly Email Draft Editor (`/reports/weekly/:week_start/email`)

- Shows LLM-generated draft with 3 sections: 業務, 〇・×, 予定.
- Subject line editable.
- Each section in a rich text area (or textarea with markdown preview).
- "Regenerate" button → re-calls LLM draft endpoint.
- "Send" button → confirmation dialog with:
  - Preview of full email
  - Recipients listed (leader + extra CCs)
  - "Send" / "Cancel" buttons
- After send: success toast. If already sent: show sent timestamp, disable send (cooldown indicator if within 5 min).

### Monthly View (`/reports/monthly/:year-month?`)

- Same dashboard components as weekly but with monthly date range.
- Month selector.
- Download button → CSV/XLSX.
- No email or AI draft — just wider time window on same views.

### Notification UI

**Bell Icon** (in header):
- Badge with unread count from `GET /api/v1/notifications/unread-count`.
- Click → dropdown panel listing recent notifications.
- Each notification: icon (by trigger type), title, time ago, read/unread indicator.
- Click notification → navigate to relevant page (e.g., record date, weekly report).
- "Mark all as read" link at top.

**Preferences** (`/settings/notifications`):
- Table: trigger types × channels (email, Teams).
- Toggle switches for each cell.
- In-app column always on (greyed out, non-toggleable).
- Save → `PUT /api/v1/notification-preferences`.

### Export UI (`/export`)

- Date range selector.
- Format selector: CSV or XLSX.
- Scope: "My records" (member) or "Team records" (leader) or "All data" (admin).
- Download button → triggers export endpoint, streams file download.

### Leader Unlock UI (`/team/unlock`)

- List of team members.
- For each member: calendar view or date list showing locked records.
- "Grant unlock" button per date → calls `POST /api/v1/unlock-grants`.
- Active unlocks shown with "Revoke" button.
- Or: simple form — select member, select date, confirm.

## Acceptance Criteria

- [ ] Weekly report dashboard with 6 metrics and download
- [ ] Email draft editor with edit, regenerate, send, and confirmation dialog
- [ ] Send cooldown display (timer if within 5 min of last send)
- [ ] Already-sent state: show timestamp, disable re-send until cooldown expires
- [ ] Monthly view with month selector and download
- [ ] Notification bell with unread badge and dropdown
- [ ] Notification click → navigate to relevant context
- [ ] Mark all as read
- [ ] Notification preference toggles per trigger × channel
- [ ] Export page with scope, format, date range selection
- [ ] Leader unlock: select member + date, grant/revoke
- [ ] All pages responsive

## Constraints

- Email language follows global setting — UI shows the draft in that language regardless of UI locale.
- Never auto-send email. User must click Send + confirm.
- Export respects visibility: members can't export other members' private fields.

## Out of Scope

- Quarterly report UI (Phase 3B)
- MS Teams notification delivery (Phase 3A backend)
- Member growth longitudinal view (use existing growth API + dashboard components)
