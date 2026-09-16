# Repository agent instructions

This file is the canonical operating guide for this repository. The project adapts the template framework to its existing architecture; template guidance is a starting point, not a mandatory structure.

## Interaction and authorization

- If the user asks a question, explain the answer without changing files or external state.
- If the user requests implementation, make the requested change within the stated scope.
- Do not mix explanation and implementation unless requested.
- Before each tool call, classify the latest user message. Questions, explanations, reviews, diagnoses, status requests, comments, and objections are read-only.
- File modification is authorized only when the user explicitly requests an action such as edit, modify, change, fix, implement, apply, rewrite, or remove.
- A question about completed work does not authorize a follow-up edit.
- If authorization or scope is ambiguous, ask whether the user wants an edit or an explanation.

## State-change boundary

- Implementation authorization is limited to editing source code, tests, and documentation.
- Do not run maintenance scripts, migrations, backfills, seed commands, database writes, deployment commands, or other state-changing operations without explicit user authorization for that specific operation.
- Tests and checks must use isolated test data and must not modify `data/jobs.db` or other user data.
- Do not commit, merge, push, deploy, or send external messages unless explicitly requested.

## Execution priorities

- State assumptions when they affect implementation.
- If multiple valid interpretations exist, present options or ask before choosing silently.
- Prefer the minimum code that solves the request; keep changes surgical and directly traceable.
- Do not refactor unrelated code or add speculative features, abstractions, or configurability.
- Treat simplicity and low maintenance cost as design goals; do not assume enterprise practices fit this local, solo-developer project.
- Weigh the concrete utility of non-trivial additions against the technical debt they create.
- For multi-step tasks, define focused verification checks and run them after implementation.
- Stop and ask when scope, requirements, or repository behavior materially conflict.

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
- Run backend tests from the repository root with `poetry run pytest`.
- Run live tests explicitly from the repository root with `poetry run pytest -m live -v -s`.

## Frontend work

- Before implementing UI changes, select the closest page pattern from `docs/modes/application/application_rules.md`.
- Apply that document's display constraints, including user-facing labels and omission of raw IDs, foreign keys, debug metadata, and unformatted timestamps.
- Reuse existing styles and components; introduce shared primitives incrementally only when they provide clear value.

## Precedence

When instructions overlap, use this order:

1. Explicit user requirements and authorization boundaries.
2. This repository guide's state-change and blocking rules.
3. `docs/project/project_rules.md`.
4. The applicable mode and core documentation.
5. General conventions and preferences.

## Command hygiene

- Use a 10-second timeout by default.
- Do not hardcode secrets in commands. Load local secrets from `.env` only when necessary.
- Do not send verbose or potentially large command output to stdout by default. Write detailed logs and reports to an appropriate file under `logs/` and tell the user where to find them. Use stdout only for concise status, errors, or output the user explicitly requested there.
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
