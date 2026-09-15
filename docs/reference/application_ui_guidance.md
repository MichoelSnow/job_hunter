# Application UI guidance

Use these patterns for new or substantially changed frontend pages. Existing pages are migrated incrementally.

## Common guidance

- Put the page title and primary action at the top.
- Show the smallest useful set of fields in collections.
- Keep filters and advanced controls secondary to the result or task.
- Provide loading, error, and empty states.
- Avoid exposing implementation details such as IDs, raw timestamps, and backend metadata.

## List

Use a page header, primary collection section, and optional filters or summary section. Keep rows and cards structurally consistent and make the empty state actionable.

## Form

Use a page header and a readable-width form section. Put required inputs first and group advanced settings separately.

## Detail

Use a page header, a summary section, and grouped secondary sections. For job details, prioritize title, company, location, arrangement, salary, score, and application actions.

## Canvas and focused interaction

Keep a workspace dominant and controls compact. Use a modal or side panel for bounded secondary actions such as application-history inspection.
