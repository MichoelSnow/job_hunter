# Framework audit

Use this as a structured, advisory review of a proposed branch. Review only changed files and the relevant code paths.

## Context

- `AGENTS.md`
- `docs/core/core_rules.md`
- `docs/project/project_rules.md`
- `docs/modes/application/application_rules.md` for UI changes

## Project scale and maintenance budget

This is a local, single-user, solo-developer application. Review proposed code, abstractions, safeguards, migrations, and operational measures in proportion to that scale. Do not recommend code or process merely for completeness, template conformity, or hypothetical future requirements.

For every non-trivial addition, weigh its concrete utility against the ongoing maintenance and technical-debt cost it introduces. Prefer the smallest safe solution that addresses a demonstrated problem. Treat added complexity as a finding only when it creates a concrete correctness, reliability, security, or maintenance risk for this repository.

Generic enterprise practices are not a default requirement. An intentional, coarse, or narrowly scoped solution is reasonable when it satisfies the user's workflow and avoids unnecessary maintenance burden.

## Checks

- Are architecture and project constraints respected?
- Is behavior unnecessarily duplicated, complex, hidden, or non-deterministic?
- For UI changes, is the page purpose clear and are loading, error, and empty states handled?
- Do new UI changes avoid raw internal data and unsafe HTML exposure?
- Are changed behaviors covered by appropriate deterministic tests?
- Were unrelated files or compatibility layers added without need?
- Does each new abstraction, safeguard, dependency, migration, or process have enough concrete utility to justify its maintenance and technical-debt cost?
- Are recommendations proportionate to a local, single-user application and its actual scale?

## Output

Return findings with severity and explain any intentional deviation from template guidance. A deviation is not automatically a failure.
