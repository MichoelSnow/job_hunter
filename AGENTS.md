# Repository agent instructions

This file is the canonical operating guide for this repository. The project adapts the template framework to its existing architecture; template guidance is a starting point, not a mandatory structure.

## Applying the framework

- Prefer explicit project requirements, current repository behavior, and user decisions over generic template defaults.
- Use template docs as guidelines. Adapt, simplify, or reject a guideline when it does not fit this repository.
- Record meaningful deviations in the relevant project documentation instead of forcing artificial compliance.
- Do not reorganize a mature part of the repository solely to match the template.

## Code writing

- Do not use emojis in code.
- Replace print statements with logging.
- Prefer small, single-responsibility functions with clear names.
- Handle empty inputs, missing data, and partial failures explicitly.
- Avoid copy-paste divergence and remove dead code introduced by changes.
- Update docs when behavior or data flows change.
- Prefer the lowest-maintenance safe solution.
- Do not add legacy compatibility code unless explicitly requested.

## Project conventions

- Use tenacity for retries when querying external APIs.
- Respect `.python-version` when pyenv is available, and verify the active interpreter is Python 3.13 before dependency, test, or backend work. Treat the `pyproject.toml` Python constraint as the compatibility authority.
- This is a local, single-user application. Do not add authentication, multi-tenancy, or an automatic scheduler unless explicitly requested.
- Keep secrets in `.env`; never hardcode or commit them.
- Before writing code or making external API calls, read relevant official API documentation. Do not guess endpoints or request shapes.

## Testing

- Add or update tests for behavior changes, new features, and bug fixes.
- Prefer deterministic unit tests for core logic and integration tests for API/database interactions.
- Test edge cases and failure modes.
- Keep real external API calls in tests marked `@pytest.mark.live`; the default suite excludes them.
- Run backend tests from `backend/` with `../.venv/bin/python -m pytest`.
- Run live tests explicitly with `../.venv/bin/python -m pytest -m live -v -s`.

## Command hygiene

- Use a 10-second timeout by default.
- Do not hardcode secrets in commands. Load local secrets from `.env` only when necessary.
- Do not use destructive commands or overwrite unrelated user changes.

## Documentation to read

- `docs/core/core_rules.md` for adapted cross-project principles.
- `docs/core/session_state.md` for concise handoff state.
- `docs/project/project_rules.md` for this repository architecture and exceptions.
- `docs/modes/application/application_rules.md` for frontend work.
- `docs/project/architecture.md` for current system structure and decisions.
- `docs/project/engineering_guide.md` for project tooling and development conventions.

## Research and external tools

- Use external tools only when required.
- Do not use Context7 unless explicitly requested.
- If browser inspection or a JS-rendered page is required, ask the user to gather the needed browser information.
