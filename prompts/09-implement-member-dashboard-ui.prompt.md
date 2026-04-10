---
mode: agent
description: "Phase 1B: Member dashboard — 5 home screen components"
---

# Task: Member Dashboard UI

## Context

The member's home screen with 5 components providing at-a-glance overview.

### Components

**1. Today's Form (quick access)**
- Shows today's record status: submitted (green), draft (yellow), empty (gray), absence (blue).
- Click → navigates to `/daily/today`.
- If not submitted: prominent "Start Today's Record" CTA.

**2. Running / Blocked Tasks**
- Card list of carry-over items (status=running or blocked from most recent record).
- Each card: task description, project, effort, status badge, days carried (count).
- Click → opens the daily form for the relevant date.

**3. Weekly Summary**
- Current week's data (Mon–today).
- Category distribution pie/donut chart (OKR / Routine / Interrupt).
- Task count, days reported out of working days so far.

**4. Personal Load Trend**
- Line chart: day_load over last 4 weeks.
- X-axis: dates. Y-axis: 1-5 scale.
- Highlight days with load ≥ 4 (warning zone).

**5. Blocker History**
- List of recent blockers (last 2 weeks).
- Columns: date, task, blocker_type, blocker_text (if visible), status.
- Blocked tasks that are now done shown with strikethrough.

### Data Fetching

All data from existing endpoints:
- `/api/v1/daily-records?user_id=me&start_date=...&end_date=...`
- `/api/v1/daily-records/carry-over`
- Task entries are nested in daily records.

### Layout

- Responsive grid: 2 columns on desktop, 1 on mobile.
- Today's form: full width top.
- Running tasks + weekly summary: side by side.
- Load trend + blocker history: side by side below.

## Acceptance Criteria

- [ ] 5 components rendering with real API data
- [ ] Today's form card with correct status indicator and CTA
- [ ] Running/blocked tasks list from carry-over endpoint
- [ ] Weekly summary with category chart
- [ ] Load trend line chart (last 4 weeks)
- [ ] Blocker history table (last 2 weeks)
- [ ] Responsive grid layout
- [ ] Loading states and empty states for each component
- [ ] Chart library integrated (e.g., recharts, chart.js, or similar)

## Constraints

- day_load is a private field — member sees their own. No visibility issue here.
- blocker_text is private — member sees their own. Show it on their own dashboard.
- Charts should be lightweight. No heavy chart library.

## Out of Scope

- Leader dashboard (next task)
- Personal growth trends over months (Phase 2B)
- Social features (Phase 3B)
