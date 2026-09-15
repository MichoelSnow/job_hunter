# job_hunter

Personal job search aggregation and tracking tool. Discovers data leadership roles in healthcare/healthtech companies in Manhattan/Brooklyn, scores them against your profile, and tracks applications.

## Setup

### Prerequisites
- Python 3.13 - the supported compatibility range is defined in pyproject.toml
- pyenv is optional. If used, select any installed Python 3.13 patch release.
- Poetry (`pip install poetry`)
- Node.js 20+ and pnpm (`npm install -g pnpm`)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:
- `JSEARCHAPI_KEY` — from [openwebninja.com](https://www.openwebninja.com/api/jsearch/docs)
- `SERPLYAPI_KEY` — from [serply.io](https://serply.io)

Edit `config/user_profile.yaml` with your name, resume path, and skills.

### 2. Select Python

If using pyenv, install and select a Python 3.13 patch release, for example:

```bash
pyenv install 3.13.15
pyenv local 3.13.15
poetry env use "$(pyenv which python)"
```

If you are not using pyenv, use any installed Python 3.13 interpreter that satisfies the `pyproject.toml` constraint and configure Poetry with it.

### 3. Create the data directory

```bash
mkdir -p data
```

Place your resume in `data/` (`.md`, `.docx`, or `.pdf` supported) and update `resume_file_path` in `config/user_profile.yaml` accordingly.

### 4. Install backend dependencies

```bash
poetry install
```

### 5. Start the backend

```bash
poetry run uvicorn main:app --reload --app-dir backend
```

API runs at http://localhost:8000. Swagger docs at http://localhost:8000/docs.

### 6. Install and start the frontend

```bash
cd frontend
pnpm install
pnpm dev
```

UI runs at http://localhost:5173.

---

## Development Commands

All commands run from the **repo root** unless noted.

### Backend

| Command | Description |
|---|---|
| `poetry run uvicorn main:app --reload --app-dir backend` | Start dev server |
| `.venv/bin/python -m pytest` | Run all backend tests |
| `.venv/bin/python -m pytest backend/tests/unit/` | Unit tests only |
| `poetry run ruff check .` | Lint |
| `poetry run ruff format .` | Format |

### Frontend (run from `frontend/`)

| Command | Description |
|---|---|
| `pnpm dev` | Start dev server |
| `pnpm build` | Production build |
| `pnpm lint` | Lint |
| `pnpm format` | Format |

## Server deployment

For an always-on Ubuntu deployment accessible from your LAN, see [docs/project/deployment.md](docs/project/deployment.md). It installs persistent user-level `systemd` services and keeps the frontend/API on one origin, suitable as a future Cloudflare Tunnel origin.

---

## Project Structure

See [docs/project/architecture.md](docs/project/architecture.md) for the full directory layout and design decisions.

## Working with the repository

The canonical agent instructions are in [AGENTS.md](AGENTS.md). Adapted framework guidance is organized under [docs/core](docs/core/), [docs/project](docs/project/), [docs/modes/application](docs/modes/application/), [docs/reference](docs/reference/), and [docs/review](docs/review/).

## Triggering a Job Search

With the backend running, trigger only paid API sources:

```bash
curl -X POST http://localhost:8000/api/jobs/refresh/apis
```

Trigger only scrapers:

```bash
curl -X POST http://localhost:8000/api/jobs/refresh/scrapers
```

To fill salary fields for existing jobs using their stored descriptions:

```bash
curl -X POST http://localhost:8000/api/jobs/backfill-salaries
```

To classify unknown work arrangements for existing jobs:

```bash
curl -X POST http://localhost:8000/api/jobs/backfill-work-arrangements
```

Or use the UI buttons: "Refresh API Jobs" and "Refresh Scraped Jobs".


## Session Start Prompt

```text
Use this repository's framework docs as the operating contract for this session while working across the full codebase.

1. Load and follow /agents.md.
2. Read and apply all required docs referenced by /agents.md.
3. If /docs/project/project_rules.md exists, load and enforce it as project-layer constraints.
4. Use /docs/core/session_state.md as canonical session continuity context:
- Continue from "Next concrete steps"
- Do not reopen completed work unless requested

Before implementation, summarize:
- docs loaded
- whether /docs/project/project_rules.md is present
- immediate next actions
