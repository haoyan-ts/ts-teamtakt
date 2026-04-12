# Contributing to ts-teamtakt

Welcome! This guide covers the conventions and workflow for contributing to this project. For a step-by-step walkthrough of the full development workflow, see [docs/how-to/contributing.md](docs/how-to/contributing.md).

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable / production-ready code. Protected. |
| `dev`  | Integration branch. All PRs target `dev`. Protected. |
| `feat/*` | New features |
| `fix/*`  | Bug fixes |
| `chore/*` | Tech debt, refactors, dependency upgrades |
| `docs/*`  | Documentation-only changes |

**Branch naming:** `<type>/<short-description>` using kebab-case.

```
feat/leader-overload-detection
fix/edit-window-grace-period
chore/upgrade-sqlalchemy-2.1
docs/add-contributing-guide
```

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer: Co-authored-by, Closes #N]
```

**Types:** `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `ci`

**Scopes:** `backend`, `frontend`, `db`, `auth`, `api`, `ui`, `notifications`, `llm`, `ci`

**Examples:**
```
feat(api): add leader unlock endpoint for daily records
fix(frontend): correct edit window countdown timer
refactor(db): extract carry-over logic to service layer
chore(deps): upgrade fastapi to 0.116
docs(how-to): add contributing guide
```

---

## Sprint Workflow

Sprints are **2 weeks** long and tracked via [GitHub Projects](https://github.com/haoyan-ts/ts-teamtakt/projects).

### Picking up work

1. Go to the sprint board and find an issue in the **Sprint Backlog** column assigned to you (or unassigned).
2. Move the issue card to **In Progress**.
3. Create a branch from `dev`:
   ```
   git checkout dev && git pull
   git checkout -b feat/your-feature-name
   ```

### During development

- Commit frequently with meaningful messages.
- Keep your branch rebased on `dev` to avoid large merge conflicts.
- Move the card to **In Review** when you open a PR.

### End of sprint

- Any unfinished work moves back to **Backlog** or gets carried to the next sprint.
- Closed issues auto-move to **Done** when the PR merges.

---

## Pull Request Process

1. **Open the PR** targeting `dev` (never directly to `main`).
2. **Fill the PR template** fully — especially the invariants checklist.
3. **CI must pass** — Backend CI (ruff + pyright + pytest) and Frontend CI (eslint + tsc).
4. **Request 1 review** from a team member. For alembic migrations, request 2.
5. **Squash and merge** is preferred to keep `dev` history clean.
6. **Link the issue** in the PR body with `Closes #<number>` so it closes automatically on merge.

---

## Definition of Done

A feature or fix is **done** when all of the following are true:

- [ ] Code is merged to `dev`
- [ ] All CI checks pass
- [ ] Related issue is closed
- [ ] Invariants checklist in the PR template is signed off
- [ ] New behavior is covered by tests (unit or integration)
- [ ] Any relevant documentation is updated

---

## Invariants Reference

Critical business rules that must never be broken are documented in [`.github/copilot-instructions.md`](.github/copilot-instructions.md). Review that file before touching:

- Edit window / lock logic
- Visibility filtering (public vs private fields)
- Carry-over snapshot immutability
- Daily record ↔ Absence mutual exclusion
- Self-assessment tag primary validation
- LLM input sanitization

---

## Versioning

This project uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH). While MAJOR is `0`, the project is under active development and not yet published.

**Canonical version** is stored in the root `pyproject.toml` and kept in sync across `backend/pyproject.toml` and `frontend/package.json` by commitizen.

### How commit types map to version increments

| Commit type | Increment | Example |
|-------------|-----------|---------|
| `fix` | patch (0.1.x) | `fix(api): correct edit window deadline` |
| `feat` | minor (0.x.0) | `feat(ui): add carry-over indicator` |
| `BREAKING CHANGE` footer | major (x.0.0) | `feat!: redesign record schema` |

### Bumping the version

Run from the **repo root** on the `dev` branch:

```bash
cz bump           # detects increment from commits, updates all version files, appends CHANGELOG.md, commits, and tags
git push && git push --tags
```

To preview what would happen without writing anything:

```bash
cz bump --dry-run
```

The tag (`v0.x.y`) moves to `main` when the release PR merges from `dev`. Do not bump directly on `main`.

---

## Development Setup

See [docs/how-to/contributing.md](docs/how-to/contributing.md) for the full environment setup guide.

Quick reference:
```bash
# Backend
cd backend && uv sync --all-groups
uv run uvicorn app.main:app --reload

# Frontend
cd frontend && yarn install
yarn dev
```
