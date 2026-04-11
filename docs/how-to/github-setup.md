---
title: "How to Set Up GitHub Project Management"
type: how-to
audience: developers
date: 2026-04-11
---

# How to Set Up GitHub Project Management

This guide runs through the one-time setup of labels, branch protection rules, a GitHub Projects v2 sprint board, and sprint milestones for ts-teamtakt. Run these commands once when bootstrapping a new instance of the repository.

## Prerequisites

- You are a **repository admin** on `github.com/haoyan-ts/ts-teamtakt`.
- The [GitHub CLI (`gh`)](https://cli.github.com/) is installed.
- You are authenticated: `gh auth login` (select GitHub.com → HTTPS → browser).

```bash
gh auth status   # should show: Logged in to github.com as <your-username>
```

---

## Steps

### 1. Create labels

Run the following commands to create all standard labels. The commands are idempotent — re-running them on an existing label will fail silently (use `--force` to overwrite).

#### Type labels

```bash
gh label create "bug"         --color "d73a4a" --description "Something is broken"
gh label create "feature"     --color "0075ca" --description "New feature or capability from the PRD"
gh label create "enhancement" --color "a2eeef" --description "Improvement to an existing feature"
gh label create "chore"       --color "e4e669" --description "Tech debt, refactor, dependency upgrade"
gh label create "docs"        --color "0052cc" --description "Documentation only"
gh label create "test"        --color "bfd4f2" --description "Test coverage or test infrastructure"
```

#### Priority labels

```bash
gh label create "P0-critical" --color "b60205" --description "System down or data loss — fix immediately"
gh label create "P1-high"     --color "e99695" --description "Major feature broken or blocking"
gh label create "P2-medium"   --color "fbca04" --description "Degraded experience, non-blocking"
gh label create "P3-low"      --color "c5def5" --description "Minor issue or cosmetic"
```

#### Component labels

```bash
gh label create "backend"       --color "1d76db" --description "Python FastAPI backend"
gh label create "frontend"      --color "0e8a16" --description "React + TypeScript frontend"
gh label create "database"      --color "5319e7" --description "PostgreSQL schema or Alembic migration"
gh label create "auth"          --color "e4e669" --description "MS365 SSO / Azure AD / OIDC"
gh label create "notifications" --color "c2e0c6" --description "Email, Teams, or in-app notifications"
gh label create "llm"           --color "d4c5f9" --description "Azure OpenAI integration"
gh label create "infra"         --color "bfd4f2" --description "Deployment, CI/CD, infrastructure"
```

#### PRD Phase labels

```bash
gh label create "phase-1A" --color "0075ca" --description "Phase 1A: Core Backend"
gh label create "phase-1B" --color "0075ca" --description "Phase 1B: Core Frontend"
gh label create "phase-2A" --color "1d76db" --description "Phase 2A: Insights & Output Backend"
gh label create "phase-2B" --color "1d76db" --description "Phase 2B: Insights & Output Frontend"
gh label create "phase-3A" --color "5319e7" --description "Phase 3A: Social & AI Backend"
gh label create "phase-3B" --color "5319e7" --description "Phase 3B: Social & AI Frontend"
```

#### Status labels

```bash
gh label create "blocked"       --color "d73a4a" --description "Cannot proceed — waiting on something"
gh label create "needs-design"  --color "fef2c0" --description "Requires design decision before implementation"
gh label create "needs-review"  --color "e4e669" --description "Needs triage or review"
gh label create "wontfix"       --color "ffffff" --description "Acknowledged but will not be addressed"
```

### 2. Set up branch protection

Protect `main` (stable) and `dev` (integration) so that no direct pushes are allowed and CI must pass before merging.

#### Protect `main`

```bash
gh api repos/haoyan-ts/ts-teamtakt/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Lint & Test (Python)","Lint & Type-check (TypeScript)"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null
```

#### Protect `dev`

```bash
gh api repos/haoyan-ts/ts-teamtakt/branches/dev/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Lint & Test (Python)","Lint & Type-check (TypeScript)"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":false}' \
  --field restrictions=null
```

> **Note:** The `contexts` strings must match the `name:` fields in `.github/workflows/ci-backend.yml` and `.github/workflows/ci-frontend.yml` exactly. If you rename a workflow, update these too.

### 3. Create the GitHub Projects v2 sprint board

GitHub Projects v2 is managed via GraphQL. Run these steps in order.

#### 3a. Get your owner node ID

```bash
gh api graphql -f query='{ viewer { login id } }'
# Note the "id" value — you'll use it below as OWNER_ID
```

For an organization:

```bash
gh api graphql -f query='{ organization(login: "YOUR_ORG") { id } }'
```

#### 3b. Create the project

```bash
gh api graphql -f query='
  mutation {
    createProjectV2(input: {
      ownerId: "OWNER_ID"
      title: "ts-teamtakt Development"
    }) {
      projectV2 { id number url }
    }
  }
'
# Note the project "id" — you'll use it below as PROJECT_ID
```

#### 3c. Add the Sprint (iteration) field

```bash
gh api graphql -f query='
  mutation {
    addProjectV2Field(input: {
      projectId: "PROJECT_ID"
      dataType: ITERATION
      name: "Sprint"
    }) {
      projectV2Field { ... on ProjectV2IterationField { id } }
    }
  }
'
```

Configure 2-week iterations in the GitHub UI: open the project → **Settings → Sprints** → set duration to **2 weeks** and set the start date to the Monday your first sprint begins.

#### 3d. Add the Priority field

```bash
gh api graphql -f query='
  mutation {
    addProjectV2Field(input: {
      projectId: "PROJECT_ID"
      dataType: SINGLE_SELECT
      name: "Priority"
      singleSelectOptions: [
        { name: "P0-critical", color: RED,    description: "System down / data loss" }
        { name: "P1-high",     color: ORANGE, description: "Major feature broken" }
        { name: "P2-medium",   color: YELLOW, description: "Degraded experience" }
        { name: "P3-low",      color: BLUE,   description: "Minor / cosmetic" }
      ]
    }) {
      projectV2Field { id }
    }
  }
'
```

#### 3e. Add the Component field

```bash
gh api graphql -f query='
  mutation {
    addProjectV2Field(input: {
      projectId: "PROJECT_ID"
      dataType: SINGLE_SELECT
      name: "Component"
      singleSelectOptions: [
        { name: "backend",       color: BLUE   }
        { name: "frontend",      color: GREEN  }
        { name: "database",      color: PURPLE }
        { name: "auth",          color: YELLOW }
        { name: "notifications", color: PINK   }
        { name: "llm",           color: GRAY   }
        { name: "infra",         color: RED    }
        { name: "multiple",      color: GRAY   }
      ]
    }) {
      projectV2Field { id }
    }
  }
'
```

#### 3f. Add the Phase field

```bash
gh api graphql -f query='
  mutation {
    addProjectV2Field(input: {
      projectId: "PROJECT_ID"
      dataType: SINGLE_SELECT
      name: "Phase"
      singleSelectOptions: [
        { name: "1A", color: BLUE   }
        { name: "1B", color: BLUE   }
        { name: "2A", color: PURPLE }
        { name: "2B", color: PURPLE }
        { name: "3A", color: GREEN  }
        { name: "3B", color: GREEN  }
      ]
    }) {
      projectV2Field { id }
    }
  }
'
```

#### 3g. Configure the Status workflow columns

The default Status field already has **Todo**, **In Progress**, and **Done** columns. Rename and add columns to match the sprint workflow:

Open the project in GitHub UI → click the **Status** field dropdown → **Edit field** → rename/add options:

| Column | Meaning |
|--------|---------|
| **Backlog** | Issues not in the current sprint |
| **Sprint Backlog** | Committed to this sprint, not started |
| **In Progress** | Actively being worked on |
| **In Review** | PR open, awaiting review |
| **Done** | Merged and closed |

### 4. Create sprint milestones

Milestones act as sprint containers in the issue tracker. Create the first four sprints (adjust the due dates to match your actual sprint calendar):

```bash
# Sprint 1: Phase 1A — DB schema, auth, user/team management
gh api repos/haoyan-ts/ts-teamtakt/milestones \
  --method POST \
  --field title="Sprint 1 — Phase 1A Core Backend (Auth & Teams)" \
  --field due_on="2026-04-25T00:00:00Z" \
  --field description="PostgreSQL schema, Alembic setup, MS365 SSO, user lifecycle, team management, role system"

# Sprint 2: Phase 1A — Daily record CRUD, carry-over, visibility, controlled lists
gh api repos/haoyan-ts/ts-teamtakt/milestones \
  --method POST \
  --field title="Sprint 2 — Phase 1A Core Backend (Records & Visibility)" \
  --field due_on="2026-05-09T00:00:00Z" \
  --field description="Daily record CRUD, task entries, carry-over logic, edit window, absence API, visibility enforcement, controlled lists, OpenAPI docs"

# Sprint 3: Phase 1B — React setup, SSO login, daily form, member dashboard
gh api repos/haoyan-ts/ts-teamtakt/milestones \
  --method POST \
  --field title="Sprint 3 — Phase 1B Core Frontend (Form & Member Dashboard)" \
  --field due_on="2026-05-23T00:00:00Z" \
  --field description="React+Vite setup, SSO login flow, daily form (submit/edit/carry-over/absence), member dashboard 5 components"

# Sprint 4: Phase 1B — Leader dashboard, controlled list UI, team join UI
gh api repos/haoyan-ts/ts-teamtakt/milestones \
  --method POST \
  --field title="Sprint 4 — Phase 1B Core Frontend (Leader Dashboard)" \
  --field due_on="2026-06-06T00:00:00Z" \
  --field description="Basic leader dashboard (balance + unreported), controlled list management UI, team join UI, i18n wiring, responsive design"
```

> Add further sprints (Phase 2A onward) as you begin planning them. Sprint milestones are created on a rolling basis — plan 1–2 sprints ahead, not the whole roadmap at once.

---

## Verify

After completing all steps:

```bash
# Labels
gh label list | wc -l          # should be 25+

# Milestones
gh api repos/haoyan-ts/ts-teamtakt/milestones | jq '.[].title'

# Branch protection
gh api repos/haoyan-ts/ts-teamtakt/branches/main/protection | jq '.required_pull_request_reviews'
gh api repos/haoyan-ts/ts-teamtakt/branches/dev/protection  | jq '.required_pull_request_reviews'

# Projects board
gh project list --owner haoyan-ts
```

Open the project URL printed during step 3b to confirm all fields and columns are visible.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `gh api` returns 404 on branch protection | Branch doesn't exist yet | Push at least one commit to `main` and `dev` before applying protection |
| GraphQL mutation returns `NOT_FOUND` for `ownerId` | Used a username instead of node ID | Re-run step 3a and copy the `id` field (starts with `U_`, not the username string) |
| CI check names don't match in branch protection | Workflow `name:` field differs | Check the exact strings in `.github/workflows/ci-backend.yml` and `.github/workflows/ci-frontend.yml` |
| `gh label create` fails on existing label | Label already exists | Add `--force` to overwrite, or skip if the existing label is correct |
| Project board fields missing after creation | GraphQL mutations not run | Re-run steps 3c–3f; fields can be added at any time |

---

## Related

- [How to Contribute to ts-teamtakt](contributing.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — branch naming, commit format, Definition of Done
- [GitHub Projects v2 documentation](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub CLI manual](https://cli.github.com/manual/)
