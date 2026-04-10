---
name: create-docs
description: "Create documentation for this repo using the Diátaxis framework. Use when asked to write, add, or create docs, documentation, a tutorial, how-to guide, reference, or explanation. Produces one Markdown file per invocation in docs/. If multiple docs are requested, creates only the first and queues the rest in docs/BACKLOG.md. If the target file already exists, queues the request as an update instead of overwriting."
argument-hint: "<doc-type> <topic> — e.g. 'how-to add a team member'"
---

# create-docs

Create one Diátaxis-compliant documentation file per invocation. All docs go in `docs/` at the repo root. Multiple requests are handled via a backlog.

See the [Diátaxis reference](./references/diataxis.md) for framework background.

---

## Diátaxis Types

| Type          | Reader's question           | Folder              |
| ------------- | --------------------------- | ------------------- |
| `tutorial`    | "Help me learn by doing"    | `docs/tutorial/`    |
| `how-to`      | "How do I accomplish X?"    | `docs/how-to/`      |
| `reference`   | "What exactly is/does X?"   | `docs/reference/`   |
| `explanation` | "Why does X work this way?" | `docs/explanation/` |

---

## Procedure

### Step 1 — Parse the request

Identify **every** doc request in the user's message (topic + type). If the type or topic is ambiguous, ask before continuing.

### Step 2 — Handle multiple requests

If the user asked for **2 or more** docs:

1. Take **only the first** request to process now.
2. For each remaining request, append to `docs/BACKLOG.md` under `## Queued`:
   ```
   - [ ] <type>: <topic> — queued YYYY-MM-DD
   ```
   If `docs/BACKLOG.md` does not exist, create it with this content first:
   ```markdown
   # Docs Backlog

   Queued documentation requests. Complete one item at a time by invoking /create-docs.

   ## Queued

   <!-- Items are added here automatically -->

   ## Done

   <!-- Move completed items here -->
   ```
3. Tell the user which items were queued before proceeding.

### Step 3 — Check for an existing file

Compute the target path using the folder from the Diátaxis Types table above:

```
docs/tutorial/<topic>.md
docs/how-to/<topic>.md
docs/reference/<topic>.md
docs/explanation/<topic>.md
```

If the file **already exists**:

- Append to `docs/BACKLOG.md` under `## Queued`:
  ```
  - [ ] UPDATE <type>: <topic> — requested YYYY-MM-DD  (file: docs/<folder>/<topic>.md)
  ```
- Tell the user the file exists and has been queued for an update.
- **Stop here — do not overwrite.**

### Step 4 — Load the template

Load the template that matches the doc type:

- `tutorial` → [./assets/tutorial-template.md](./assets/tutorial-template.md)
- `how-to` → [./assets/how-to-template.md](./assets/how-to-template.md)
- `reference` → [./assets/reference-template.md](./assets/reference-template.md)
- `explanation` → [./assets/explanation-template.md](./assets/explanation-template.md)

### Step 5 — Generate and confirm draft outline

Show the user:

1. **Proposed filename**: `docs/<folder>/<topic>.md` (use the folder from the Diátaxis Types table)
2. **YAML frontmatter** (populated)
3. **Section outline**: H2 headings only, one sentence per section describing its purpose

Then ask: **"Proceed with this structure? (yes / no / edit)"**

Do not create the file until the user confirms.

### Step 6 — Write the file

After confirmation, create the file at the target path with:

- Complete YAML frontmatter (see format below)
- Full content following the template structure, tailored to the specific topic
- No placeholder text — write real, complete sentences throughout

---

## File Naming Rules

- Folder: `docs/tutorial/`, `docs/how-to/`, `docs/reference/`, `docs/explanation/`
- Filename: kebab-case noun phrase, e.g. `add-team-member.md`, `daily-record-schema.md`
- No type prefix in filename — the folder IS the type

## Frontmatter Format

```yaml
---
title: "<Human-readable title>"
type: tutorial | how-to | reference | explanation
audience: developers | api-consumers | maintainers | all
date: YYYY-MM-DD
---
```

