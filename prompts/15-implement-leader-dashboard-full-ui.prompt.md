---
mode: agent
description: "Phase 2B: Full leader dashboard with 6 metric components and configuration UIs"
---

# Task: Full Leader Dashboard UI

## Context

Expand the basic leader dashboard (task 10) to show all 6 metric components with configurable thresholds and balance target settings.

### 6 Dashboard Components

**1. Team Category Balance** (exists from task 10 — enhance)
- Stacked bar chart: per-member category distribution.
- Team aggregate row.
- **Overlay: configured target lines** (e.g., OKR 70% dashed line).
- Color-coded: green (within 5% of target), yellow (5-15% off), red (>15% off).
- Data: `GET /api/v1/teams/{id}/metrics/balance`

**2. Overload Detection**
- Alert cards: members with high day_load streaks.
- Each card: member name, streak length, max load, date range.
- Sorted by severity (longest streak first).
- Data: `GET /api/v1/teams/{id}/metrics/overload`

**3. Blocker Summary**
- Pie chart: blocker type distribution.
- Table: recurring blockers (same task blocked for multiple days).
- Data: `GET /api/v1/teams/{id}/metrics/blockers`

**4. Fragmentation**
- Table: members × dates where task count exceeded threshold.
- Highlight cells in calendar heatmap view.
- Data: `GET /api/v1/teams/{id}/metrics/fragmentation`

**5. Carry-over Aging**
- Table: stale tasks with working days aged, project, member.
- Sorted by age (oldest first). Color: yellow (near threshold), red (over).
- Data: `GET /api/v1/teams/{id}/metrics/carryover-aging`

**6. Project Effort Overview**
- Horizontal bar chart: effort per project.
- Cross-team projects show own team's contribution only.
- Expandable: per-member breakdown within each project.
- Data: `GET /api/v1/teams/{id}/metrics/project-effort`

### Configuration UIs

**Balance Targets** (`/team/settings/balance`)
- Per top-level category: slider or input for target %.
- Must sum to 100% (or allow partial — some categories might not have targets).
- Save → `PATCH /api/v1/teams/{id}/settings`

**Metric Thresholds** (`/team/settings/thresholds`)
- Form fields:
  - Overload: load threshold (1-5), streak days (1-10)
  - Fragmentation: task threshold (1-20)
  - Carry-over aging: days threshold (1-30)
- Current values pre-filled from team settings.
- Save → `PATCH /api/v1/teams/{id}/settings`

### Layout

- Date range selector at top (default: current week). Applies to all components.
- 2×3 grid on desktop, stacked on mobile.
- Settings accessible via gear icon in header.

## Acceptance Criteria

- [ ] All 6 metric components rendering with real API data
- [ ] Category balance with target overlay lines and color coding
- [ ] Overload alert cards sorted by severity
- [ ] Blocker pie chart + recurring blockers table
- [ ] Fragmentation table/heatmap
- [ ] Carry-over aging table with color indicators
- [ ] Project effort bar chart with expandable member breakdown
- [ ] Balance target configuration UI (sliders/inputs)
- [ ] Metric threshold configuration UI
- [ ] Date range selector affecting all components
- [ ] Responsive grid layout
- [ ] Loading and empty states for each component

## Constraints

- Leader sees own team data only.
- Cross-team project effort: leader sees own team's contribution only.
- All thresholds have sensible defaults — configuration is optional.

## Out of Scope

- Sharing privilege UI (Phase 4)
- Member growth trends (same page, separate task below)
