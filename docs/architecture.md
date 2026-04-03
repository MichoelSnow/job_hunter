# Architecture

## Overview

Single-user, locally-run job search aggregation tool. No authentication, no multi-tenancy. The user runs the backend and frontend on their own machine.

---

## Directory Structure

```
job_search/
├── backend/
│   ├── app/
│   │   ├── api/                  # FastAPI routers, one file per resource group
│   │   │   ├── __init__.py
│   │   │   ├── jobs.py
│   │   │   ├── applications.py
│   │   │   ├── companies.py
│   │   │   ├── criteria.py
│   │   │   ├── user.py
│   │   │   └── analytics.py
│   │   ├── services/             # Business logic — no FastAPI imports
│   │   │   ├── __init__.py
│   │   │   ├── api_aggregator.py
│   │   │   ├── scraper/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── greenhouse.py  # Greenhouse boards JSON API
│   │   │   │   ├── lever.py       # Lever postings JSON API
│   │   │   │   └── html_scraper.py # Fallback HTML scraping
│   │   │   ├── job_filter.py
│   │   │   ├── text_parser.py
│   │   │   └── scoring_engine.py
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── job.py
│   │   │   ├── company.py
│   │   │   ├── application.py
│   │   │   ├── criteria.py
│   │   │   └── tracking.py
│   │   ├── schemas/              # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   ├── job.py
│   │   │   ├── application.py
│   │   │   ├── company.py
│   │   │   └── criteria.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   └── session.py        # SQLAlchemy engine + session factory
│   │   └── config/
│   │       └── settings.py       # pydantic-settings; single source of truth
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_job_filter.py
│   │   │   ├── test_scoring_engine.py
│   │   │   └── test_text_parser.py
│   │   └── integration/
│   │       └── test_api.py
│   └── main.py                   # FastAPI app entry point
├── frontend/
│   ├── src/
│   │   ├── components/           # Reusable UI pieces
│   │   │   ├── JobCard.jsx
│   │   │   ├── JobList.jsx
│   │   │   ├── JobDetails.jsx
│   │   │   ├── JobFilters.jsx
│   │   │   ├── ApplicationForm.jsx
│   │   │   └── Dashboard.jsx
│   │   ├── pages/                # Route-level components
│   │   │   ├── JobsPage.jsx
│   │   │   ├── ApplicationsPage.jsx
│   │   │   ├── CompaniesPage.jsx
│   │   │   └── SettingsPage.jsx
│   │   ├── hooks/                # React Query data-fetching hooks
│   │   │   ├── useJobs.js
│   │   │   └── useApplications.js
│   │   ├── services/
│   │   │   └── api.js            # Axios client + all API calls
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── config/
│   ├── user_profile.yaml         # Name, resume path, skills (edited manually)
│   └── skill_taxonomy.json       # Skill normalization taxonomy
├── data/                         # SQLite DB lives here (gitignored)
├── docs/
│   ├── architecture.md           # This file
│   ├── engineering_guide.md
│   └── project_plan.md
├── pyproject.toml                # Poetry — single Python dependency file
├── .env                          # Secrets (gitignored)
├── .env.example
└── README.md
```

---

## Key Design Decisions

### Single-User, No Auth
This tool runs locally for one person. There is no `users` table and no authentication layer. User identity (name, resume path, skills) lives in `config/user_profile.yaml`, which is edited manually. All criteria and application data live in the DB and are managed through the UI.

### Persistent Database Across Search Sessions
The SQLite database accumulates data across all job search sessions — whether the user runs it weekly, returns after 3 months, or picks it up again a year later. Jobs are never purged; they remain with their `discovered_date` timestamp. The UI defaults to showing jobs from the last 60 days, with a date filter to expand the view. Applications and history are always preserved.

This means no concept of "search sessions" at the schema level — `discovered_date` on each job row is sufficient to scope any time window.

For scraper-sourced jobs, if a role disappears from a successful scrape for that company/source, the job is marked closed by setting `closed_date` to that scrape date. If the role reappears in a later scrape, `closed_date` is cleared.

Scraper target settings are sourced from the `companies` DB table (edited via the Companies page), including Workday board/instance and HTML selectors.

### DB Migrations
Schema is recreated freely during Phases 0–5. Alembic will be added in Phase 6 once the schema stabilizes.

### Job Refresh: Manual Trigger Only
`POST /api/jobs/refresh/apis` triggers paid API discovery (JSearch + Serply) as a FastAPI `BackgroundTask`.
`POST /api/jobs/refresh/scrapers` triggers scraper discovery (Greenhouse/Lever/Workday).
No automated scheduler is in scope. Weekly execution cadence is a cost-estimation guideline, not an automated schedule.

### User Criteria: DB Only
Job search criteria are stored in the `user_criteria` table and managed exclusively through the Settings UI. There is no parallel YAML file for criteria — the DB is the single source of truth.

### Scoring Weights: settings.py Only
All scoring weights are defined in `backend/app/config/settings.py` with defaults. They are injected into `ScoringEngine` at construction. They are not in `.env` and not hardcoded inside service classes.

---

## Technology Choices

### Backend
- **Python 3.13** — latest stable
- **Poetry** — dependency management (`pyproject.toml`)
- **FastAPI** — async REST API with built-in OpenAPI docs
- **SQLAlchemy** — ORM; sessions injected via FastAPI `Depends`
- **SQLite** — embedded, zero-config; Alembic added in Phase 6
- **pydantic-settings** — typed config loaded from `.env`
- **tenacity** — retry logic for all external API calls
- **requests** — HTTP client for job APIs and scrapers
- **beautifulsoup4 + lxml** — HTML scraping fallback
- **spaCy** — NER and text processing for resume/JD parsing
- **scikit-learn** — TF-IDF vectorization, cosine similarity
- **sentence-transformers** (`all-MiniLM-L6-v2`) — local semantic embeddings for Phase 2 scoring; no API cost, ~80 MB model
- **python-docx + pypdf** — resume file parsing

### Frontend
- **React 18** — UI framework
- **Vite** — build tool
- **Tailwind CSS + shadcn/ui** — styling and components
- **React Query (TanStack Query)** — server state and caching
- **Zustand** — minimal local UI state
- **Axios** — HTTP client
- **react-router-dom** — routing
- **TanStack Table** — job list table with sorting/filtering

### Tooling
- **ruff** — Python linting and formatting (replaces black + pylint)
- **pytest + httpx** — backend testing
- **ESLint + Prettier** — frontend linting and formatting
- **gitleaks** — secret scanning in CI

---

## Job Discovery: Source Priority

For company-specific scrapers, use public ATS JSON APIs before falling back to HTML scraping:

1. **Greenhouse boards API** — `https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs`
   - Returns structured JSON, no scraping needed
   - Many healthcare/healthtech companies (Oscar Health, Flatiron, etc.)

2. **Lever postings API** — `https://api.lever.co/v0/postings/{company_id}?mode=json`
   - Returns structured JSON
   - Also widely used in healthtech

3. **Ashby posting API** — `https://api.ashbyhq.com/posting-api/job-board/{job_board_name}?includeCompensation=true`
   - Returns full job posting fields (description HTML/plain, published date, job/apply URLs, compensation)
   - Preferred over Ashby non-user GraphQL brief listings

4. **HTML scraping** — `beautifulsoup4` + `lxml`, fallback only for companies with no public ATS API

Each company row stores `ats_type` and `ats_id` so the scraper layer can dispatch without endpoint probing.

---

## Scoring Architecture

### Phase 1 (rule-based + TF-IDF)
- spaCy NER extracts skills/titles from job descriptions and resume
- Keyword taxonomy (`config/skill_taxonomy.json`) maps terms to normalized skill categories
- TF-IDF cosine similarity computes skill overlap between user profile and job requirements
- Rule-based dimension scores (experience years, title level, salary, location) combine with weighted formula

### Phase 2 (semantic embeddings)
- `sentence-transformers` `all-MiniLM-L6-v2` runs locally — no API calls, no cost
- Encode user skill set and job description as dense vectors
- Cosine similarity in embedding space replaces or augments TF-IDF
- Fallback to Phase 1 if model not loaded

### Weight Configuration
All weights live in `backend/app/config/settings.py` as typed fields with defaults. `ScoringEngine` accepts a `Settings` instance at construction — no globals, no env lookups inside the service.

```
overall_score = (user_to_job_score × user_to_job_weight) + (job_to_user_score × job_to_user_weight)
```

---

## Environment Variables (`.env`)

Only secrets and environment-specific values belong in `.env`. Scoring weights stay in `settings.py`. Discovery queries/locations and hard filter toggles are user-managed via `/api/settings/discovery` and stored in the database.

```bash
# Database
DATABASE_URL=sqlite:///./data/jobs.db

# API Keys
RAPIDAPI_KEY=your_rapidapi_key_here

# Application
DEBUG=True
CORS_ORIGINS=http://localhost:5173
```

---

## User Profile (`config/user_profile.yaml`)

Edited manually once during setup; loaded at startup by `text_parser` and `scoring_engine`.

```yaml
user:
  name: "Your Name"
  resume_file_path: "data/resume.docx"

skills:
  technical:
    - name: "Python"
      category: "data_engineering"
      proficiency: "expert"
    - name: "SQL"
      category: "data_engineering"
      proficiency: "expert"
  leadership:
    - "team management"
    - "stakeholder management"
    - "roadmap planning"
  domain:
    - "healthcare analytics"
    - "HIPAA"
    - "EHR"

experience_years: 10
current_title: "Director of Data"
```
