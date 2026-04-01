# job_search

Personal job search aggregation and tracking tool. Discovers data leadership roles in healthcare/healthtech companies in Manhattan/Brooklyn, scores them against your profile, and tracks applications.

## Setup

### Prerequisites
- Python 3.13+
- Poetry (`pip install poetry`)
- Node.js 20+ and pnpm (`npm install -g pnpm`)

### 1. Clone and configure

```bash
cp .env.example .env
# Add your RAPIDAPI_KEY to .env
```

Edit `config/user_profile.yaml` with your name, resume path, and skills.

### 2. Backend

```bash
poetry install
poetry run uvicorn backend.main:app --reload
```

API runs at http://localhost:8000. Swagger docs at http://localhost:8000/docs.

### 3. Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

UI runs at http://localhost:5173.

## Development Commands

All backend commands run from the **repo root**.

### Backend

| Command | Description |
|---|---|
| `poetry run uvicorn backend.main:app --reload` | Start dev server |
| `poetry run pytest` | Run all tests |
| `poetry run pytest backend/tests/unit/` | Unit tests only |
| `poetry run ruff check .` | Lint |
| `poetry run ruff format .` | Format |

### Frontend (run from `frontend/`)

| Command | Description |
|---|---|
| `pnpm dev` | Start dev server |
| `pnpm build` | Production build |
| `pnpm lint` | Lint |
| `pnpm format` | Format |

## Project Structure

See [docs/architecture.md](docs/architecture.md) for the full directory layout and design decisions.

## Triggering a Job Search

With the backend running, hit the refresh endpoint:

```bash
curl -X POST http://localhost:8000/api/jobs/refresh
```

Or use the UI once Phase 4 is implemented.
