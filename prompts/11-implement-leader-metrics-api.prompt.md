---
mode: agent
description: "Phase 2A: Leader metrics APIs — overload, fragmentation, carry-over aging, blockers, balance, project effort"
---

# Task: Leader Metrics APIs

## Context

Six metric APIs for the leader dashboard, with configurable thresholds per team.

### Endpoints

All scoped to leader's team (or all teams for admin).

**1. Overload Detection**
`GET /api/v1/teams/{id}/metrics/overload?start_date=&end_date=`
- Returns members with `day_load ≥ threshold` for `streak+` consecutive days within range.
- Response: `[{ user_id, display_name, streak_start, streak_end, max_load }]`

**2. Blocker Summary**
`GET /api/v1/teams/{id}/metrics/blockers?start_date=&end_date=`
- Response: `{ by_type: [{ type, count }], recurring: [{ task_desc, project, days_blocked }] }`

**3. Fragmentation**
`GET /api/v1/teams/{id}/metrics/fragmentation?start_date=&end_date=`
- Returns days where member logged ≥ threshold tasks.
- Response: `[{ user_id, display_name, date, task_count }]`

**4. Carry-over Aging**
`GET /api/v1/teams/{id}/metrics/carryover-aging`
- Returns currently running/blocked tasks aged beyond threshold.
- **Aging = calendar working days from chain root's record_date to today.**
- Chain root: follow `carried_from_id` to the origin (where carried_from_id IS NULL).
- Working days: exclude weekends + holidays (holiday calendar table or weekend-only for now).
- Response: `[{ user_id, display_name, task_desc, project, root_date, working_days_aged }]`

**5. Category Balance**
`GET /api/v1/teams/{id}/metrics/balance?start_date=&end_date=`
- Per-member category distribution (% of total effort by top-level category).
- Team aggregate.
- Comparison vs configured targets.
- Response: `{ members: [{ user_id, categories: { OKR: 65, Routine: 30, Interrupt: 5 } }], team_aggregate: {...}, targets: { OKR: 70, Routine: 30 } }`

**6. Project Effort Overview**
`GET /api/v1/teams/{id}/metrics/project-effort?start_date=&end_date=`
- Effort per project, including cross-team aggregate (own team contribution for leader).
- Response: `[{ project_id, name, scope, total_effort, member_effort: [...] }]`

### Configurable Thresholds

**Settings Endpoints:**
- `GET /api/v1/teams/{id}/settings` — get current thresholds
- `PATCH /api/v1/teams/{id}/settings` — update (leader/admin)

**Settings model** (per team):
```
team_settings:
  team_id FK (UNIQUE)
  overload_load_threshold (int, default 4)
  overload_streak_days (int, default 3)
  fragmentation_task_threshold (int, default 8)
  carryover_aging_days (int, default 5)
  balance_targets JSONB (default { "OKR": 70, "Routine": 30 })
```

### Member Growth APIs

- `GET /api/v1/users/me/growth?months=3` — personal trends: category balance evolution, load trend, blocker reduction over months.
- Same data as leader metrics but scoped to self only.

## Acceptance Criteria

- [ ] All 6 metric endpoints returning correct data
- [ ] Overload: streak detection with configurable threshold
- [ ] Carry-over aging: follows chain to root, counts working days (not links)
- [ ] Balance: per-member + aggregate + target comparison
- [ ] Team settings CRUD with defaults
- [ ] Metrics use team's thresholds, not hardcoded values
- [ ] Leader scoped to own team; admin can query any team
- [ ] Member growth endpoint scoped to self only
- [ ] Cross-team project effort: leader sees own team's contribution only
- [ ] Tests: each metric with edge cases, threshold overrides, empty data

## Constraints

- Carry-over aging = calendar working days from chain root, not chain link count.
- Balance targets at top-level category only (not sub-types).
- No effort gaming guardrails — trust the data, leader addresses via 1:1.

## Out of Scope

- Dashboard UI for these metrics (Phase 2B)
- Holiday calendar integration for carry-over aging (use weekend-only filter for now)
- Sharing privilege implementation (task 14)
