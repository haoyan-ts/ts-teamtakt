# PRD: Task Entity Layer & GitHub Integration

## Status: Proposed
## Date: 2026-04-12

---

## 1. Problem Statement

The current `TaskEntry` model conflates two distinct concerns:

- **Task** — what needs to happen (multi-day, outcome-based, may span multiple reports)
- **Daily log** — what I actually did today on that task (one-day, effort-based)

The carry-over chain (`carried_from_id`) is a structural workaround: it snapshots a task's state into each new day's record. This creates duplicate rows, makes task-level aggregation difficult, and provides no natural home for non-code tasks (hardware, physical work, admin) that are central to robotics teams.

At the same time, the team uses GitHub Issues/Projects for coordination. There is no formal bridge, so GitHub and ts-teamtakt describe the same work in parallel with no connection.

---

## 2. Goals

1. Introduce a first-class **Task** entity that persists across days.
2. Make `DailyWorkLog` the daily dimension — what I did on a given task on a given day.
3. Support non-issue tasks (hardware, lab work, admin) as equally first-class as software tasks.
4. Enable GitHub Issue URL → TaskEntry auto-fill when the user pastes an issue URL.
5. Preserve all existing invariants: edit window, visibility, self-assessment tags, carry-over aging signal.

---

## 3. Out of Scope

- Real-time bidirectional sync with GitHub (no webhooks, no write-back to GitHub)
- GitHub Project board embedding in ts-teamtakt UI
- Hardware-specific fields beyond category/sub-type (physical location, part numbers, etc.)

---

## 4. New Data Model

### 4.1 `tasks` (new table)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `title` | Text NOT NULL | Free text or auto-filled from GitHub Issue title |
| `description` | Text NULL | For display only; never injected into LLM |
| `assignee_id` | FK users NOT NULL | Single owner |
| `project_id` | FK projects NOT NULL | |
| `category_id` | FK categories NOT NULL | |
| `sub_type_id` | FK category_sub_types NULL | |
| `status` | ENUM(todo, running, done, blocked) NOT NULL | Current state of the task |
| `estimated_effort` | Int 1–5 NULL | Planned effort; from GitHub Project custom field if linked |
| `blocker_type_id` | FK blocker_types NULL | Current blocker classification |
| `github_issue_url` | Text NULL | **Immutable after set**. Triggers auto-fill on form |
| `created_by` | FK users NOT NULL | |
| `created_at` | DateTime NOT NULL | |
| `closed_at` | Date NULL | Set when status transitions to `done` |
| `is_active` | Bool default true | Soft-delete |

**Constraints:**
- `UNIQUE(assignee_id, github_issue_url) WHERE github_issue_url IS NOT NULL` — prevents the same issue being linked to multiple tasks for the same user.
- `github_issue_url` is immutable after first set (app-level enforcement, same pattern as `carried_from_id`).

### 4.2 `daily_work_logs` (replaces `task_entries`)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `task_id` | FK tasks NOT NULL | Parent task |
| `daily_record_id` | FK daily_records NOT NULL | Parent daily record |
| `effort` | Int 1–5 NOT NULL | **Actual** effort spent today (not estimated) |
| `work_note` | Text NULL | What specifically happened today |
| `blocker_type_id` | FK blocker_types NULL | Today's blocker (overrides task-level for this day) |
| `blocker_text` | Text NULL | Private free text (owner + leader + admin only) |
| `sort_order` | Int NOT NULL | |
| UNIQUE | `(task_id, daily_record_id)` | One log per task per day |

### 4.3 `daily_work_log_self_assessment_tags` (replaces `task_entry_self_assessment_tags`)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `daily_work_log_id` | FK daily_work_logs NOT NULL | |
| `self_assessment_tag_id` | FK self_assessment_tags NOT NULL | |
| `is_primary` | Bool NOT NULL | Exactly one `true` per daily_work_log (invariant preserved) |
| UNIQUE | `(daily_work_log_id, self_assessment_tag_id)` | |

### 4.4 `projects` (additive change only)

Add one nullable column:

| Field | Type | Notes |
|---|---|---|
| `github_repo` | Text NULL | e.g. `"org/repo-name"`. Used to map repository → project_id at auto-fill time |

### 4.5 Removed

| Removed | Reason |
|---|---|
| `task_entries` table | Replaced by `tasks` + `daily_work_logs` |
| `task_entries.carried_from_id` | Task entity makes carry-over a UI concept, not a schema concept |
| `task_entries.task_description` | Moved to `tasks.title` |
| `task_entries.category_id/sub_type_id/project_id/status` | Moved to `tasks` |

---

## 5. Invariants (Updated)

| Invariant | New Form |
|---|---|
| `carried_from_id` immutable | `github_issue_url` immutable after set |
| Carry-over aging = working days from chain root to today | Aging = working days from `Task.created_at` (or first `DailyWorkLog` date) to today |
| Exactly one `is_primary=true` per task per day | Exactly one `is_primary=true` per `DailyWorkLog` |
| Private fields stripped by role | `blocker_text` and `day_load` still private; `DailyWorkLog.blocker_text` follows same rule |

---

## 6. GitHub Integration: Auto-Fill Flow

When the user pastes a GitHub Issue URL into the "New Task" dialog:

1. Backend fetches Issue via GitHub API (title, labels, state, repository, linked Project item)
2. GitHub Project custom field values read (requires `github_repo` configured on Project)
3. Auto-fill mapping:

| GitHub field | Fills | Confidence |
|---|---|---|
| `issue.title` | `Task.title` | High |
| `issue.repository` + `Project.github_repo` | `Task.project_id` | High (if configured) |
| Project custom field `Category` | `Task.category_id` | High (if label matches category name) |
| Project custom field `Sub-type` | `Task.sub_type_id` | High |
| Project custom field `Effort` | `Task.estimated_effort` | High |
| `issue.state=closed` | `Task.status=done` | High |
| Project custom field `Blocker Type` | `Task.blocker_type_id` | Medium |
| `issue.state=open` | `Task.status=todo` (suggested) | Low — user confirms |

4. User reviews pre-filled fields, corrects status to `running` if already started, saves Task.
5. On the daily form, user adds a `DailyWorkLog` for that Task — fills **actual effort** and self-assessment tag.

**GitHub Project custom field naming convention** (admin responsibility):
- Field names in GitHub Project must exactly match ts-teamtakt category/sub-type/blocker-type names.
- ts-teamtakt controlled lists are authoritative. When admin changes a name, the GitHub Project field option is updated manually.
- Mapping is stored in `team_settings` JSON column under key `github_field_map`:
  ```json
  {
    "category_field": "Category",
    "sub_type_field": "Sub-type",
    "effort_field": "Effort",
    "blocker_type_field": "Blocker Type"
  }
  ```

---

## 7. Daily Form Flow (Updated)

1. Member opens daily form for a date.
2. System shows all active Tasks (`status ≠ done`, `assignee = me`) as pre-populated rows.
3. Member adds a `DailyWorkLog` for each task touched today:
   - Required: `effort` (actual), at least one self-assessment tag with one `is_primary=true`
   - Optional: `work_note`, blocker override
4. Member skips tasks not touched — no entry required.
5. Member can add a new Task inline:
   - Free text → hardware/admin task (no GitHub link)
   - Paste GitHub Issue URL → auto-fill flow
6. Member fills `day_load` (whole-day feeling) and `day_note`, submits.

No carry-over UI needed. Active tasks are always visible. "Done" tasks disappear from the form automatically.

---

## 8. Reporting Impact

| Report | Change |
|---|---|
| Category balance | Computed from `DailyWorkLog.effort` joined through `Task.category_id` — same signal |
| Carry-over aging | Computed from `Task.created_at` to today (working days) — simpler, no chain traversal |
| Leader dashboard | Can now show per-task effort history and estimated vs. actual effort delta |
| Weekly email | Aggregate `DailyWorkLog` rows per week per user — same structure |
| Quarterly report | Richer: can describe tasks by outcome (Task.title) with daily effort breakdown |

---

## 9. Acceptance Criteria

- [ ] `tasks` table exists with all fields above; `github_issue_url` is immutable after set at app layer
- [ ] `daily_work_logs` table exists; `UNIQUE(task_id, daily_record_id)` enforced
- [ ] `daily_work_log_self_assessment_tags` preserves exactly-one-primary invariant
- [ ] `projects.github_repo` nullable column added
- [ ] GitHub Issue URL paste triggers auto-fill (title, project, category, sub_type, estimated_effort)
- [ ] Daily form shows all active tasks for the user without a separate carry-over step
- [ ] Tasks with `status=done` are hidden from the daily form (but accessible in task history)
- [ ] Visibility rules unchanged: `blocker_text` and `day_load` remain private
- [ ] Carry-over aging computed correctly from `Task.created_at`
- [ ] All existing tests updated; no `task_entries` references remain
- [ ] Alembic migration provided with safe rollback path (data migration from `task_entries` if any seed data exists)
