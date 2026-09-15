# Job Hunter project plan

This document is the current roadmap and product context. It is intentionally less detailed than the original bootstrap specification. Current behavior is authoritative in [architecture.md](architecture.md), and completed work is tracked in [implementation_checklist.md](implementation_checklist.md).

## Product

Job Hunter is a personal, local application that discovers data leadership roles in healthcare and healthtech, filters them against location and work-arrangement preferences, scores them against a matching profile, and tracks applications.

The primary user wants in-office or hybrid opportunities in Manhattan and Brooklyn and needs to reduce the time spent searching multiple job sources and evaluating fit.

## Current system

- Backend: Python 3.13, FastAPI, SQLAlchemy, and SQLite.
- Frontend: React 19, Vite, Tailwind CSS, and TanStack Query/Table.
- Discovery: paid API sources plus public ATS scrapers for supported companies.
- Processing: normalization, filtering, resume/job-description parsing, and profile-to-job scoring.
- Settings: persisted in the single-user `user_settings` record and managed through the Settings UI.
- Job refresh: manually triggered API and scraper refresh endpoints; no scheduler is currently in scope.
- Deployment: local development or the documented Ubuntu systemd setup in [deployment.md](deployment.md).

See [architecture.md](architecture.md) for the authoritative directory layout, data flow, environment variables, and design decisions.

## Completed foundation

The implementation checklist records the detailed status. The current foundation includes:

- FastAPI backend and SQLite persistence.
- API and ATS discovery integrations with normalization and retry handling.
- Job filtering and deduplication.
- Resume parsing and profile-to-job scoring.
- Jobs, companies, applications, settings, and analytics screens.
- Application status history and resume upload flow.
- Deployment scripts and frontend/API same-origin configuration.

## Near-term priorities

1. Stabilize remaining scraper and parsing edge cases.
2. Improve user-facing error, loading, and empty states.
3. Improve the consistency of the frontend layout incrementally as pages are changed.
4. Add database migrations once the schema has stabilized.
5. Improve operational documentation and backup/restore procedures for the local SQLite database.

## Later possibilities

These are ideas, not current requirements:

- Additional job-source integrations and company scrapers.
- More advanced matching and local semantic scoring.
- Search and application analytics.
- Optional notifications or digest generation.
- Public deployment only after authentication, data-protection, and network-security requirements are addressed.

Do not implement these items implicitly. Confirm scope and update the architecture before starting work that changes the single-user or local-only assumptions.

## Success measures

- Reduce time spent on recurring job searches.
- Surface relevant roles with useful location and work-arrangement filtering.
- Make fit scoring explainable through matched and missing skills.
- Preserve application history and job discovery history across refreshes.
- Keep recurring operating cost and maintenance low.
