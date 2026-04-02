## Code writing instructions
 - Do not use emojis in any code
 - Replace print statements with logging
 - When trying to fix code through multiple iterations make sure to clean up the old iterations before trying something new
 - Remove dead code immediately after refactors
 - Prefer single-responsibility functions with clear names
 - Avoid copy-paste divergence across files
 - Handle edge cases explicitly (empty inputs, missing data, partial failures)
 - Update docs when behavior or data flows change
 - Prefer the lowest-maintenance solution that is still safe and acceptable for production use.
 - Avoid introducing recurring operational toil (manual rotations, frequent audits, brittle workflows) unless the user explicitly requests it or it is mandatory for core security/safety.
 - For security and reliability work, favor simple, durable controls with clear defaults and minimal ongoing upkeep.

### Python Specific Instructions
 - Use tenacity for retries when querying APIs




## Testing expectations
 - Add or update tests whenever behavior changes, new features are introduced, or bugs are fixed
 - Prefer unit tests for core logic; add integration tests when multiple modules interact
 - Test edge cases and failure modes (empty inputs, invalid configs, missing data, etc.)
 - Keep tests deterministic; seed randomness and avoid network calls
 - Add lightweight smoke tests for new workflows or CLI paths
 - If tests are skipped, state why and provide a manual verification step
 - Use pytest by default for Python; keep tests fast and isolated
 - ALWAYS run pytest as `.venv/bin/python -m pytest` from the `backend/` directory. Never use `poetry run pytest`, `python -m pytest`, or any other invocation — they will fail due to the poetry/pyenv version mismatch in this project.
 - Tests that make real external API calls must be marked `@pytest.mark.live`. The default pytest run excludes `live` tests (`-m 'not live'` is set in pyproject.toml). To run live tests explicitly: `.venv/bin/python -m pytest -m live -v -s`

## Command hygiene
 - Run shell commands with a 10-second timeout by default.
 - If a command exceeds 10 seconds, stop and ask the user to run it manually; do not change implementation solely to force the command under 10 seconds.
 - If a long-running command is interrupted or times out, check for partial artifacts (e.g., `node_modules` temp dirs) and either clean the affected paths or recommend a clean install before retrying.
 - Never hardcode secrets in commands. Always reference values from environment variables (loaded via `set -a; source .env; set +a`).

## MCPs
  - Only use the Context7 MCP when I explicitly ask for it

## Research before acting

- Before writing code or running commands that interact with an external API or service,
  read its documentation first. If official docs are not available, say so and ask the
  user how to proceed — do not probe with speculative requests.
- Never guess API endpoints, request shapes, or authentication by trial and error.
  Each failed attempt wastes time and context. One well-read doc beats ten curl attempts.
- If a task requires inspecting a JS-rendered page or a browser session (e.g. DevTools
  Network tab), say so immediately and ask the user to gather that information. Do not
  attempt to replicate browser behavior with curl.
- Limit external verification commands to what can succeed in ≤ 3 attempts with a clear
  hypothesis for each. If the third attempt fails, stop and report what is unknown rather
  than continuing to guess.