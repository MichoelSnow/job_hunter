# Core rules

These rules apply to all work in this repository.

## Engineering

- Prefer the simplest implementation that satisfies the requirement.
- Keep behavior explicit and deterministic; document intentional non-determinism.
- Reuse established project patterns before introducing abstractions.
- Avoid copy-paste divergence and remove superseded code when a change replaces it.
- Keep business logic out of HTTP routers and React page components. Backend behavior belongs in `backend/app/services/`; frontend API access belongs in `frontend/src/services/`.
- Do not create a new top-level directory without updating `docs/project/architecture.md`.

## Documentation

- Keep one authoritative home for each rule, contract, or design decision.
- Update existing docs rather than creating overlapping documents.
- Keep operating instructions concise; put rationale and examples in `docs/reference/`.
- Update affected documentation when behavior, data flow, commands, or file locations change.

## Security and privacy

- This is a local, single-user application; do not add authentication or multi-tenant machinery unless the project scope changes.
- Never commit secrets or expose them in logs, errors, or API responses. Use `.env` for local secrets and `.env.example` for placeholders.
- Validate external API responses and user-provided settings at the boundary.
- Use parameterized queries or ORM operations and safe HTML handling.
- Treat resume data, application notes, and job-search settings as sensitive local data.

## Testing

- Add or update tests for behavior changes, including edge and failure cases.
- Prefer deterministic unit tests for services and integration tests for API/database behavior.
- Keep external API calls out of the default test run; live tests must be explicitly marked.
- Use the repository-specific test command in `AGENTS.md`.
