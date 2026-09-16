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
- Write verbose operational output, reports, and long-running task logs to files under `logs/` rather than stdout. Keep stdout limited to concise status or errors unless a command explicitly documents another output format.

## Backend testing

- Use pytest with httpx for API tests and direct unit tests for services.
- Test validation, empty results, malformed data, partial source failures, retries, and database state transitions where relevant.
- Keep real external API calls in tests marked `@pytest.mark.live`.
- The default suite excludes live tests through the pytest configuration.
- Run from the repository root using the Poetry-managed environment:

  ```bash
  poetry run pytest
  ```

- Run live tests explicitly when credentials and network access are available:

  ```bash
  poetry run pytest -m live -v -s
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

Ruff selects the `E`, `F`, `I`, and `UP` rule families with no temporary
exclusions. Keep new and modified backend code compliant with the configured
line length, import ordering, and modern typing rules.

From `frontend/`:

```bash
pnpm lint
pnpm format
```

Poetry and pnpm are the dependency-management authorities. Do not add a second lockfile or package-manager workflow without an explicit reason.

## External APIs and scrapers

- Read the relevant official API documentation before changing an integration.
- Use tenacity for retries on external API calls.
- Paid API requests use a maximum 60-second timeout and at most one retry for
  transient timeout, connection, or server-side HTTP failures; client and rate-
  limit errors are not retried. Provider response and quota diagnostics are
  logged without credentials or full payloads.
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

Run backend maintenance scripts from `backend/` with Poetry. To normalize locations for historic jobs while preserving their original values:

```bash
poetry run python -m scripts.update_historic_locations --dry-run
poetry run python -m scripts.update_historic_locations
```

The dry run is optional but recommended before committing the update. The operation is rerunnable and only updates rows whose normalized value or preserved raw value changes.

To report existing duplicate job snapshots without changing the database:

```bash
poetry run python -m scripts.cleanup_duplicate_jobs
```

The script writes its output to `logs/cleanup_duplicate_jobs.log` rather than stdout.

The cleanup matches snapshots by normalized application URL plus normalized description, or by company, title, and normalized description across sources. Description normalization collapses whitespace, normalizes common bullet characters, and performs a second-pass similarity check for descriptions that are at least 99% similar. It prefers a company ATS/API source (`ashby`, `greenhouse`, `lever`, or `workday`) over an aggregator such as JSearch, then keeps the earliest discovered row. It preserves descriptions below that similarity threshold and skips groups linked to applications. After reviewing the dry-run output, pass `--apply` to remove later duplicates:

```bash
poetry run python -m scripts.cleanup_duplicate_jobs --apply
```

`--apply` is the only mode that deletes rows and must be run explicitly.

## Continuous integration

GitHub Actions runs on pushes to `main` and pull requests. It installs Python
3.13 and Poetry, then runs:

- backend pytest (`poetry run pytest`)
- backend Ruff (`poetry run ruff check backend`)
- frontend Vitest (`pnpm test`)
- frontend ESLint (`pnpm lint` through `pnpm check`)
- frontend production build (`pnpm build` through `pnpm check`)

Live backend tests remain excluded from CI unless explicitly selected.
