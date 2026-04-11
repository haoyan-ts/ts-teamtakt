---
title: "How to Contribute to ts-teamtakt"
type: how-to
audience: developers
date: 2026-04-11
---

# How to Contribute to ts-teamtakt

This guide walks you through the complete workflow for contributing to ts-teamtakt — from picking up an issue on the sprint board to getting your PR merged.

## Prerequisites

- Local development environment is running. Follow [How to Set Up the Local Development Environment](local-dev-setup.md) first.
- You have a GitHub account with access to the [ts-teamtakt repository](https://github.com/haoyan-ts/ts-teamtakt).
- `git` is installed and configured with your GitHub credentials.
- The GitHub CLI (`gh`) is installed for interacting with the sprint board from the terminal (optional but useful).

---

## Steps

### 1. Find an issue to work on

Open the [sprint board](https://github.com/haoyan-ts/ts-teamtakt/projects) and look at the **Sprint Backlog** column. Pick an issue that is:

- Unassigned, or explicitly assigned to you.
- Labelled with the current sprint's phase (e.g. `phase-1A`).
- Within your scope (check the `backend` / `frontend` label).

If you have questions about an issue's requirements, leave a comment on the issue before starting.

### 2. Assign yourself and move the card

On the issue page:

1. Assign yourself under **Assignees**.
2. In the sprint board, drag the card from **Sprint Backlog** to **In Progress**.

Or from the terminal:

```bash
gh issue edit <number> --add-assignee @me
```

### 3. Create a branch from `dev`

Always branch from `dev` — never from `main`.

```bash
git checkout dev
git pull origin dev
git checkout -b <type>/<short-description>
```

Branch type prefixes:

| Prefix | When to use |
|--------|------------|
| `feat/` | New feature or enhancement |
| `fix/`  | Bug fix |
| `chore/` | Tech debt, refactor, dependency upgrade |
| `docs/` | Documentation only |

Examples:

```bash
git checkout -b feat/leader-overload-detection
git checkout -b fix/edit-window-grace-period
git checkout -b docs/add-api-reference
```

### 4. Develop and commit

Make your changes. Commit frequently using [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

Common types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `ci`  
Common scopes: `backend`, `frontend`, `db`, `auth`, `api`, `ui`, `notifications`, `llm`

Examples:

```bash
git commit -m "feat(api): add leader unlock endpoint for daily records"
git commit -m "fix(frontend): correct edit window countdown timer"
git commit -m "refactor(db): extract carry-over logic to service layer"
```

**Before each commit**, make sure local checks pass:

```bash
# Backend
cd backend
uv run ruff check .
uv run pyright
uv run pytest

# Frontend
cd frontend
yarn lint
yarn tsc --noEmit
```

### 5. Keep your branch up to date

If `dev` has moved forward while you were working, rebase to avoid conflicts:

```bash
git fetch origin
git rebase origin/dev
```

Resolve any conflicts, then continue:

```bash
git rebase --continue
```

### 6. Push and open a pull request

```bash
git push origin <your-branch>
```

Then open a PR on GitHub targeting `dev`:

```bash
gh pr create --base dev --title "feat(api): add leader unlock endpoint" --body ""
```

Or open it in the browser. GitHub will detect your branch and pre-fill the base branch.

**Fill in the PR template fully.** Pay special attention to:

- Linking the issue: add `Closes #<number>` in the body.
- The **invariants checklist** — review [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md) if unsure.

### 7. Pass CI checks

Two CI jobs run on every PR:

| Job | What it checks |
|-----|---------------|
| **Backend CI** | ruff lint + format, pyright type check, pytest |
| **Frontend CI** | ESLint, TypeScript `tsc --noEmit` |

Only the relevant job runs based on which files changed — a backend-only PR won't trigger the frontend check.

If a check fails, click **Details** on the failing check, read the error, fix it locally, and push again. The CI reruns automatically.

### 8. Request a review

Request at least **1 reviewer**. For changes to `backend/alembic/` (database migrations), request **2 reviewers**.

Move your sprint board card from **In Progress** to **In Review**.

### 9. Address review feedback

If changes are requested:

1. Make the changes on your branch.
2. Push the updated commits.
3. Re-request review once ready (use the 🔄 button next to the reviewer's name).

### 10. Merge

Once approved and CI passes, **squash and merge** into `dev`. The linked issue closes automatically.

Move your card to **Done** if it didn't close automatically.

After merging, clean up your local branch:

```bash
git checkout dev
git pull origin dev
git branch -d <your-branch>
```

---

## Verify

Your contribution is complete when:

- The PR is merged to `dev`.
- The linked GitHub issue is closed.
- The sprint board card is in **Done**.
- CI is green on `dev`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| CI fails with `ruff` errors | Code style violations | Run `uv run ruff check --fix .` locally and commit the fixes |
| CI fails with `pyright` errors | Type errors | Fix type errors; use `assert obj is not None` to narrow Optional types rather than casting |
| CI fails with `tsc` errors | TypeScript type errors | Run `yarn tsc --noEmit` locally to see full error list |
| `git push` rejected (non-fast-forward) | Someone pushed to `dev` after you branched | Run `git fetch origin && git rebase origin/dev`, resolve conflicts, then push with `git push --force-with-lease` |
| PR shows merge conflicts | Branch is behind `dev` | Rebase onto `dev` (see step 5) |
| Forgot to link an issue in the PR | Merged without `Closes #N` | Manually close the issue and move the sprint card |

---

## Related

- [How to Set Up the Local Development Environment](local-dev-setup.md)
- [How to Set Up GitHub Project Management](github-setup.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — quick reference for branch naming, commit format, and Definition of Done
- [Product Requirements Document](../PRD.md) — PRD and phased backlog
