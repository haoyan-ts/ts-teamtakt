## What changed and why

<!-- Briefly describe the change and the motivation behind it. Link the related issue with "Closes #<number>". -->

Closes #

## Type of change

<!-- Keep only the applicable type. Delete the rest. -->

- Bug fix
- New feature
- Refactor / tech debt
- Documentation
- CI/CD / infra
- Dependency upgrade

## Component(s) affected

<!-- Keep only the affected components. Delete the rest. -->

- backend
- frontend
- database schema / migration
- auth
- notifications / email
- LLM integration

## Testing done

<!-- Describe what you tested and how. For backend changes, mention which test files were run. For frontend changes, describe manual testing steps. Keep only the applicable items. Delete the rest. -->

- Existing tests pass (`uv run pytest` / `yarn lint && tsc --noEmit`)
- New tests added
- Manually tested locally

## Invariants checklist

<!-- Review the invariants in .github/copilot-instructions.md. Keep only the items that apply to this change. Delete inapplicable items. -->

- Edit window lock logic untouched or correctly updated
- Private fields (`day_load`, `blocker_text`) stripped for non-owners/non-leaders
- WebSocket visibility uses the same filter as REST
- Exactly one `is_primary=true` tag per `DailyWorkLog` enforced (if work log code touched)
- Soft-delete pattern used (no hard-delete on controlled lists)
- LLM user content injected in `<user_data>` delimiters (if LLM code touched)
- N/A — none of the above apply to this change

## Screenshots (UI changes only)

<!-- Attach before/after screenshots for any frontend changes. Delete this section if not applicable. -->
