# Engineering guide

This is the project-specific reference for coding standards, testing, tooling, and workflow. The repository is a personal, local job-search application; guidance is scaled to that context.

## Source of truth

- Current architecture and design decisions: [architecture.md](architecture.md)
- Current implementation status: [implementation_checklist.md](implementation_checklist.md)
- Current roadmap and future direction: [project_plan.md](project_plan.md)
- Local deployment: [deployment.md](deployment.md)
- Python interpreter selection: `.python-version` for pyenv exact local selection and `pyproject.toml` for the supported compatibility range
- Python dependencies and test configuration: `pyproject.toml`
- Frontend dependencies and scripts: `frontend/package.json`

## Code standards

- Prefer small functions with clear names and one responsibility.
- Keep backend business logic in `backend/app/services/`, not in FastAPI routers.
- Keep frontend API access in `frontend/src/services/`, not scattered across page components.
- Use Python type hints for public interfaces and clear JavaScript naming.
- Handle empty input, missing data, malformed external responses, and partial failures explicitly.
- Avoid circular imports, speculative abstractions, and copy-paste implementations.
- Remove dead code introduced by a change.

## Logging and errors

- Use the project logger instead of `print` statements.
- Return user-safe error messages from the API and UI.
- Log enough context to diagnose scraper, API, parsing, and database failures without logging secrets or sensitive resume content.
- Do not silently treat a failed external source as a successful empty result.

## Backend testing

- Use pytest with httpx for API tests and direct unit tests for services.
- Test validation, empty results, malformed data, partial source failures, retries, and database state transitions where relevant.
- Keep real external API calls in tests marked `@pytest.mark.live`.
- The default suite excludes live tests through the pytest configuration.
- Run from `backend/`:

  ```bash
  ../.venv/bin/python -m pytest
  ```

- Run live tests explicitly when credentials and network access are available:

  ```bash
  ../.venv/bin/python -m pytest -m live -v -s
  ```

## Frontend testing and checks

The frontend has lightweight Vitest unit tests plus lint and build checks. For frontend changes, run:

```bash
pnpm test
pnpm check
```

The individual commands remain available as `pnpm lint` and `pnpm build`. Add focused component tests when behavior becomes sufficiently complex to warrant them; CI currently gates frontend changes on tests, lint, and production build success.

When frontend behavior becomes sufficiently complex to warrant tests, add focused React tests for filters, loading/error/empty states, application updates, and API failure handling.

## Formatting and linting

From the repository root:

```bash
poetry run ruff check .
poetry run ruff format .
```

From `frontend/`:

```bash
pnpm lint
pnpm format
```

Poetry and pnpm are the dependency-management authorities. Do not add a second lockfile or package-manager workflow without an explicit reason.

## External APIs and scrapers

- Read the relevant official API documentation before changing an integration.
- Use tenacity for retries on external API calls.
- Prefer stable public ATS APIs before HTML scraping.
- Normalize and validate source data before persistence.
- Keep API keys in `.env` and do not include them in logs, fixtures, or tests.

## Data and API contracts

- Pydantic schemas under `backend/app/schemas/` define API payload contracts.
- SQLAlchemy models under `backend/app/models/` define persisted entities.
- Coordinate backend and frontend changes when a response shape changes.
- Preserve application history and discovered jobs unless a retention policy is explicitly introduced.
- Schema changes currently occur during the active development phase; Alembic is planned only after the schema stabilizes.

## Security and privacy

- This is local and single-user today; authentication is not part of the current application.
- Treat resume files, application notes, settings, and API keys as sensitive.
- Validate uploaded resume paths and content types.
- Sanitize job-description HTML before rendering it in the frontend.
- Do not expose database IDs, raw backend metadata, secrets, or debug details in new user-facing UI.

## Workflow

- Keep changes focused and preserve unrelated working-tree changes.
- Update the relevant project documentation when behavior or data flow changes.
- Use [implementation_checklist.md](implementation_checklist.md) for phased work status rather than duplicating task lists elsewhere.
- Review changes with the advisory guidance under `docs/review/` when useful; it is not an automatic merge gate.

## Database maintenance scripts

Run backend maintenance scripts from `backend/` with the project virtualenv. To normalize locations for historic jobs while preserving their original values:

```bash
../.venv/bin/python -m scripts.update_historic_locations --dry-run
../.venv/bin/python -m scripts.update_historic_locations
```

The dry run is optional but recommended before committing the update. The operation is rerunnable and only updates rows whose normalized value or preserved raw value changes.

## Continuous integration

GitHub Actions runs on pushes to `main` and pull requests. It installs Python 3.13 and Poetry, runs the backend pytest suite and Ruff, then installs the frontend with pnpm and runs `pnpm check` (ESLint plus the Vite production build). Live backend tests remain excluded from CI unless explicitly selected.
