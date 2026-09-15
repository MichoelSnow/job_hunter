# Review guidance

This directory defines an optional, structured review process for proposed changes. The documents are guidelines for improving confidence and consistency; they are not automatic merge gates.

## Recommended execution order

1. `01_framework_audit.md`
   - Checks alignment with the adapted project and application guidance.
   - Identifies important deviations from project rules.

2. `02_engineering_review.md`
   - Identifies bugs, security issues, data risks, missing tests, and regressions.

3. `03_exploratory_review.md`
   - Provides optional, non-blocking design and maintainability feedback.

The framework audit should be run before the engineering review when both are requested, so basic project alignment is established first. A finding is not automatically a reason to block a change; assess it against project scope, risk, and intentional design decisions.

## Required context

Reviews should use:

- `AGENTS.md`
- `docs/core/core_rules.md`
- `docs/project/project_rules.md`
- `docs/modes/application/application_rules.md` for frontend changes
- Relevant project authorities under `docs/project/`
- Relevant reference guidance under `docs/reference/`

Review only the changed files and the relevant code paths for the proposed branch. Use the repository’s actual base branch when `main` is not the correct comparison point.

## Framework audit prompt

```text
Run docs/review/01_framework_audit.md as an advisory review.
Review only files changed against the appropriate base branch.
Use:
- AGENTS.md
- docs/core/core_rules.md
- docs/project/project_rules.md
- docs/modes/application/application_rules.md for UI changes
- relevant docs/project and docs/reference material

Return:
- concise summary
- findings grouped by severity
- intentional deviations that are reasonable for this repository
- recommended follow-up actions

Do not treat a deviation from template guidance as a failure unless it conflicts with explicit project requirements or creates a concrete risk.
```

## Engineering review prompt

```text
Run docs/review/02_engineering_review.md.
Review only changed files and the relevant code paths.
Use full repository context to assess impact.
Use AGENTS.md, docs/project/project_rules.md, and the relevant project and reference docs.

Focus on bugs, security risks, data integrity, error handling, performance or cost risks, missing tests, and breaking changes.
Return severity-grouped findings and a concise readiness assessment.
Prioritize concrete risks over stylistic preferences.
```

## Exploratory review prompt

```text
Run docs/review/03_exploratory_review.md.
Review only changed files and the relevant code paths.
Use full repository context to assess architecture and maintainability impact.
Use AGENTS.md, docs/project/project_rules.md, and the relevant project and reference docs.

Provide:
- a concise change summary
- high-level assessment
- key observations
- soft risks
- thoughtful author questions
- optional improvements

Keep all feedback non-blocking unless a concrete defect is identified.
```
