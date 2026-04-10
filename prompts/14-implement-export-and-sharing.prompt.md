---
mode: agent
description: "Phase 2A: CSV/Excel export, bulk export, leader-to-leader sharing privilege"
---

# Task: Data Export & Sharing Privilege

## Context

Export endpoints for members, leaders, and admins. Plus the leader-to-leader sharing privilege system.

### Export Endpoints

**Member Export**
`GET /api/v1/export/my-records?start_date=&end_date=&format=csv|xlsx`
- Exports own daily records + task entries for date range.
- CSV: flat rows (one per task entry, record fields repeated).
- XLSX: sheet 1 = records, sheet 2 = task entries linked by record_id.

**Leader Team Export**
`GET /api/v1/export/team/{team_id}?start_date=&end_date=&format=csv|xlsx`
- All team members' records (all fields including private — leader has access).
- Same format as member export but with user column.

**Admin Bulk Export**
`GET /api/v1/export/bulk?format=csv|xlsx`
- All data: users, teams, records, tasks, absences, controlled lists.
- XLSX: one sheet per table.
- For backup/migration.

### Sharing Privilege

**Model**: `sharing_grants(id, granting_leader_id, granted_to_leader_id, team_id, granted_at, revoked_at)`

- A leader grants another leader read access to their team's individual-level data.
- **Non-transitive**: grantee sees data but cannot re-share.
- **Revocable**: granting leader sets `revoked_at` at any time.
- One active grant per (granting_leader, granted_to, team): `UNIQUE(granting_leader_id, granted_to_leader_id, team_id) WHERE revoked_at IS NULL`.

**Endpoints**
- `POST /api/v1/sharing-grants` — grant access (leader only, for own team)
- `GET /api/v1/sharing-grants` — list active grants (granted by me + granted to me)
- `DELETE /api/v1/sharing-grants/{id}` — revoke (only the granting leader or admin)

**Integration with Visibility**

When a leader with an active sharing grant queries another team's records:
- They see individual-level data (all fields including private) for the granted team.
- Without a grant: they see only cross-team project aggregates (own team's contribution).
- Update the visibility filter function (from task 06) to check sharing_grants.

## Acceptance Criteria

- [ ] Member export: CSV and XLSX for own records
- [ ] Leader team export: all team members, all fields
- [ ] Admin bulk export: all tables
- [ ] XLSX with proper sheets and headers
- [ ] CSV with proper escaping
- [ ] Sharing grant CRUD: create, list, revoke
- [ ] Non-transitivity enforced: grantee cannot create a grant for data they received via sharing
- [ ] Visibility filter updated: shared leaders see individual data for granted team
- [ ] Without grant: only cross-team aggregates visible
- [ ] Unique constraint: one active grant per (granter, grantee, team)
- [ ] Tests: export formats, sharing grant flow, visibility with/without grant, non-transitivity

## Constraints

- Sharing is point-to-point, not transitive. Grantee cannot re-share.
- Leader can only grant access to their own team's data.
- Admin sees all — no sharing grant needed.
- Export includes only data the requester has permission to see.

## Out of Scope

- Sharing privilege UI (Phase 4)
- Streaming/pagination for very large exports (optimize later if needed)
