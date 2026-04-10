---
mode: agent
description: "Phase 1B: Daily form UI — submit, edit, carry-over, absence, edit window"
---

# Task: Daily Form UI

## Context

The primary data entry screen. Members submit daily records with tasks, effort, blockers, and day_load. Includes carry-over pre-fill, absence marking, and edit window awareness.

### Form Layout

**Header**: Date selector (defaults to today). If absence exists for selected date → show "Absence recorded: {type}" badge, form disabled with "Remove absence to enter a daily record" link.

**Task List** (repeatable section):
- Category dropdown (from `/categories` — active only, with sub-types nested)
- Project dropdown (from `/projects` — filtered by visibility)
- Task description (text input)
- Effort (1-5 selector, e.g., radio buttons or slider)
- Status (todo / running / done / blocked)
- Blocker type dropdown (visible when status=blocked, from `/blocker-types`)
- Blocker text (visible when status=blocked, textarea)
- Self-assessment tags (multi-select chips, one must be marked primary)
- Carried-over indicator (badge if `carried_from_id` is set, non-editable)
- Drag handle for reordering (→ sort_order)

**Day Load**: 1-5 selector (private field — show privacy indicator icon)

**Day Note**: Textarea (public field)

**Actions**: Add task, Remove task, Submit, Save draft (local only)

### Carry-over Pre-fill

On load for a new date with no existing record:
1. Call `GET /api/v1/daily-records/carry-over`.
2. Pre-fill returned tasks into the form with `carried_from_id` set.
3. User can modify, complete, or remove any carried task.
4. "Carried from {date}" badge on each pre-filled task.

### Absence Toggle

- Button/link: "Mark as absence" → shows absence type selector → calls `POST /absences`.
- If absence exists: show type badge, "Remove absence" button → `DELETE /absences/{id}`, then re-enable form.

### Edit Window Awareness

- On load: compute if within edit window (client-side check for UX, server enforces).
- If < 30 min before Saturday 00:00 JST → show countdown warning banner.
- Record `form_opened_at` timestamp on form load, send with submit.
- If window expired → show locked state with "Contact your leader for unlock" message.
- If unlock exists → show "Unlocked by {leader}" badge, allow editing.

### Self-Assessment Tag Primary Selection

- Multi-select tag chips. One chip must be starred/marked as primary.
- If user tries to submit without exactly one primary → inline error on the offending task.

## Acceptance Criteria

- [ ] Full form with all fields as described
- [ ] Task list: add, remove, reorder (drag or up/down)
- [ ] Category → sub-type cascading dropdown
- [ ] Project dropdown filtered by user's visibility scope
- [ ] Carry-over pre-fill on empty dates with visual indicator
- [ ] Absence toggle (create/remove) integrated into date header
- [ ] Edit window: countdown warning, locked state, unlock badge
- [ ] form_opened_at captured and sent with submit
- [ ] Self-assessment tag multi-select with primary enforcement
- [ ] Blocker fields appear only when status=blocked
- [ ] Privacy indicator on day_load field
- [ ] Form validation: all required fields, effort 1-5, exactly one primary tag per task
- [ ] Responsive: works on mobile (stacked layout)

## Constraints

- carried_from_id badge is display-only, not editable.
- form_opened_at is set once on mount, not updated on re-render.
- Client-side edit window check is for UX only — server is the authority.

## Out of Scope

- Activity feed / social features (Phase 3B)
- Notifications (Phase 2B)
- Offline support
