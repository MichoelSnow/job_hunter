# job_search

Personal job search aggregation and tracking tool. Discovers data leadership roles in healthcare/healthtech companies in Manhattan/Brooklyn, scores them against your profile, and tracks applications.

## Setup

### Prerequisites
- Python 3.13 (via pyenv or system install — **not 3.14**, several ML deps don't support it yet)
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

### 2. Create the data directory

```bash
mkdir -p data
```

Place your resume in `data/` (`.md`, `.docx`, or `.pdf` supported) and update `resume_file_path` in `config/user_profile.yaml` accordingly.

### 3. Install backend dependencies

```bash
poetry install
```

### 4. Start the backend

```bash
poetry run uvicorn main:app --reload --app-dir backend
```

API runs at http://localhost:8000. Swagger docs at http://localhost:8000/docs.

### 5. Install and start the frontend

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

---

## Project Structure

See [docs/architecture.md](docs/architecture.md) for the full directory layout and design decisions.

## Triggering a Job Search

With the backend running, hit the refresh endpoint:

```bash
curl -X POST http://localhost:8000/api/jobs/refresh
```

Or use the UI once Phase 4 is implemented.
