# Session state

Use this file as concise handoff context for multi-step work. Update it when a work session materially changes the task state.

## Current objective

- Keep the project-specific documentation framework aligned with the current repository as architecture and behavior evolve.

## Integration decisions

- Template guidance is optional and may be adapted or rejected when it does not fit this repository.
- Existing architecture, project docs, and user decisions remain authoritative.

## Open work

- After the current location normalization/filtering and CI changes are merged, clean up the existing Ruff violations and remove or narrow the temporary `E501`, `I001`, and `UP043` exclusions. Restore stricter lint enforcement in CI when that cleanup is complete.

## Resume prompt

Use `docs/core/session_state.md` for concise context, then continue from the current objective and open work.
