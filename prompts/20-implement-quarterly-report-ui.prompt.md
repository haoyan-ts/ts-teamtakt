---
mode: agent
description: "Phase 3B: Quarterly report review/edit UI, guidance input, finalize flow"
---

# Task: Quarterly Report UI

## Context

Frontend for reviewing, editing, and finalizing AI-generated quarterly reports.

### Quarterly Report Page (`/reports/quarterly/:quarter?`)

**Quarter Selector**: dropdown (e.g., 2026Q1, 2025Q4). Defaults to current quarter.

**Generation Panel** (if no report exists for selected quarter):
- "Generate Quarterly Report" button.
- Guidance text input: textarea with character counter (max 2000 chars).
  - Placeholder: "Optional: guide the AI — e.g., 'emphasize mentoring role', 'highlight G1 project'"
- On submit → calls generate endpoint. Show loading spinner with progress message.

**Report View** (if report exists):

Status badge: `Generating` (spinner) | `Draft` (yellow) | `Finalized` (green)

**Per-project sections** (accordion/tabs):
Each project:
1. **定性的サマリー** (Qualitative summary) — editable rich text
2. **定量的ハイライト** (Quantitative highlights) — read-only system data + editable LLM commentary
3. **評価ポイント** (Evaluation points) — editable rich text

**Overall section**:
4. **四半期総合評価** (Quarterly overall evaluation) — editable rich text

**Actions**:
- "Save Draft" — saves edits without finalizing
- "Regenerate" — re-runs LLM (optionally with updated guidance). Confirmation: "This will overwrite current draft content."
- "Finalize" — confirmation dialog: "Once finalized, this report becomes visible to your leader. Continue?"
  - Sets status=finalized. After finalize: editing disabled, "Finalized on {date}" badge shown.

### Member Self-View

- Member sees own reports (all statuses).
- Can edit only while status=draft.
- Finalized reports are read-only.

### Leader View (`/team/quarterly/:quarter?`)

- Quarter selector + team member list.
- Shows only **finalized** reports from team members.
- Each member's report expandable (same layout as member view but read-only).
- Members without finalized reports shown as "Pending".

### Language

- Report content in global output language (from admin settings).
- Section headers in output language.
- UI chrome (buttons, labels) in user's UI language.

## Acceptance Criteria

- [ ] Quarter selector with default to current quarter
- [ ] Generation panel with guidance textarea (2000 char limit + counter)
- [ ] Loading state during generation
- [ ] Report view with per-project accordion sections
- [ ] Editable sections (rich text or markdown textarea) in draft status
- [ ] Read-only quantitative highlights (system data)
- [ ] Overall evaluation section
- [ ] Save draft, regenerate (with confirmation), finalize (with confirmation)
- [ ] Finalized = read-only with badge and timestamp
- [ ] Leader view: team member list with finalized reports only
- [ ] "Pending" indicator for members without finalized reports
- [ ] Responsive layout

## Constraints

- Output language follows global setting, not UI locale.
- Drafts are private — leader view shows only finalized.
- Guidance text max 2000 chars — enforce on frontend with counter.
- Regenerate overwrites draft — require confirmation.

## Out of Scope

- PDF export of quarterly report
- Comparison across quarters
- Admin view of all quarterly reports
