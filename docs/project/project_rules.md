# Project rules

These rules add project-specific context to the core and application guidance. The project-specific documents in this directory are the authorities for current architecture, engineering workflow, deployment, and planning.

## Existing architecture

This repository predates the template folder convention. Use this mapping without reorganizing the project solely to match the template:

- Interface: `backend/app/api/`, `backend/main.py`, `frontend/src/pages/`, and `frontend/src/App.jsx`.
- Application and domain services: `backend/app/services/`.
- Persistence and contracts: `backend/app/models/`, `backend/app/schemas/`, and `backend/app/db/`.
- Shared configuration and frontend API client: `backend/app/config/` and `frontend/src/services/`.

The current architecture is authoritative; the template layer model is a reasoning aid.

## Product constraints

- The application is local, single-user, and SQLite-backed.
- Job refresh is manually triggered. Do not describe or implement an automatic scheduler without an explicit request.
- `config/user_profile.yaml` and the `user_settings` flow are the source of truth for matching-profile behavior.
- Preserve application history and discovered jobs unless a retention policy is explicitly requested.

## UI migration rule

- Existing pages may retain their current structure until they are otherwise changed.
- For new or substantially modified pages, use the application patterns when they provide value.
- Shared layout primitives may be introduced incrementally under `frontend/src/components/ui/`; do not retrofit untouched pages as part of unrelated work.
