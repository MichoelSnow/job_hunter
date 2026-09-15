# Framework audit

Use this as a structured, advisory review of a proposed branch. Review only changed files and the relevant code paths.

## Context

- `AGENTS.md`
- `docs/core/core_rules.md`
- `docs/project/project_rules.md`
- `docs/modes/application/application_rules.md` for UI changes

## Checks

- Are architecture and project constraints respected?
- Is behavior unnecessarily duplicated, complex, hidden, or non-deterministic?
- For UI changes, is the page purpose clear and are loading, error, and empty states handled?
- Do new UI changes avoid raw internal data and unsafe HTML exposure?
- Are changed behaviors covered by appropriate deterministic tests?
- Were unrelated files or compatibility layers added without need?

## Output

Return findings with severity and explain any intentional deviation from template guidance. A deviation is not automatically a failure.
