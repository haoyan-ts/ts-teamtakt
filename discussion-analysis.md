# Discussion Analysis: GitHub Projects Methodology ↔ TeamTakt Integration

_Date: 2026-04-17_

---

## Already Covered (No Action Needed)

| Discussion Concept                                                 | TeamTakt Equivalent                                                                    |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| "Complete Issue-ification" of all work (hardware, admin, meetings) | Task entity with `category_id` / `sub_type_id` already supports non-code tasks equally |
| Human adds subjective assessment                                   | `day_load` (1–5), `day_note`, self-assessment tags, `work_note`, `blocker_text`        |
| GitHub Issue → daily report connection                             | `github_issue_url` on Task + auto-fill flow (PRD §6)                                   |
| Custom field mapping (Category, Effort)                            | `github_field_map` in `team_settings` JSON already planned                             |
| Repo-level project mapping                                         | `projects.github_repo` column already exists                                           |

---

## Complementary Concepts Worth Implementing

### 1. Automatic Activity Collection (discussion §3-①)

The discussion proposes a GitHub Actions job at 17:00 that collects status changes (`Done`, `In Progress` with updates) and pre-populates a draft.

**TeamTakt gap:** Currently, the daily form shows all active tasks, but doesn't know which ones the user actually touched today on GitHub. The user must manually add `DailyWorkLog` entries.

**Proposed integration:**

- A lightweight "daily activity sync" endpoint that queries the GitHub GraphQL API for the user's activity on a given date (issue state changes, PR reviews, commits)
- Pre-check tasks the user likely worked on → suggest them in the daily form as pre-populated `DailyWorkLog` rows with effort left blank
- Preserves TeamTakt's philosophy: **auto-collect facts, human adds meaning** (effort, self-assessment, blocker)

### 2. `insight` Field on Task (discussion §2)

The discussion adds an `Insight` custom field on GitHub Projects — a short learning per task.

**TeamTakt gap:** `work_note` exists on `DailyWorkLog` but is scoped to a single day. There is no task-level "what I learned from this" field.

**Proposed integration:**

- Add `insight` (Text, nullable, ≤500 chars) to the `tasks` table
- Displayed in quarterly reports and task history
- Auto-filled from GitHub Project custom field if configured in `github_field_map`

### 3. `Department` / Cross-functional Tracking (discussion §2)

The discussion proposes a `Department` field to measure time spent helping other departments.

**TeamTakt gap:** `Project.scope` (personal/team/cross_team) partially covers this, but doesn't capture which external department.

**Recommendation: Defer.** `cross_team` scope + project name already implies the department. Add only if the team explicitly asks for department-level aggregation in reports.

### 4. Management Repo as Catch-All (discussion §4)

The discussion proposes a dedicated "Management Repo" for non-code tasks (slides, procurement, lab work).

**TeamTakt position:** Tasks without `github_issue_url` are already first-class. Non-code tasks do not need a GitHub Issue.

**Recommendation:** This is an **organizational practice**, not a system feature. Document it as a team convention. Users who want to link management issues can; those who don't create tasks directly in TeamTakt.

---

## Conflicting Concepts (Resolved)

### PR-Based Submission vs. Edit Window

The discussion uses PR merge as the "submit" trigger. TeamTakt uses a server-side edit window with lock formula (`week_start + 12 days → Saturday 00:00 JST`).

**Resolution:** Incompatible. TeamTakt's edit window is an invariant — it handles grace periods, leader unlocks, and absence records. The PR workflow is elegant for a git-based system but cannot enforce these constraints. **Keep TeamTakt's edit window.**

### GitHub Actions as Report Engine vs. TeamTakt Backend

The discussion puts report generation in GitHub Actions. TeamTakt has its own backend with weekly/quarterly report generation triggered after the edit window closes.

**Resolution:** TeamTakt's backend is the report engine. GitHub is a _data source_, not the orchestrator. Activity collection (concept #1 above) should be a TeamTakt backend service, not a GitHub Action.

---

## Recommended Priority Order

1. **Implement GitHub auto-fill** — already planned; `github_autofill.py` is stubbed and the `/tasks/autofill` endpoint returns HTTP 501
2. **Add daily activity suggestion endpoint** — query GitHub for today's user activity, pre-suggest work log entries (effort left blank for human input)
3. **Add `insight` field to Task** — small schema change, high value for quarterly reports
4. **Defer department-level tracking** — wait for explicit team demand
