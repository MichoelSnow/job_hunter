# Application mode rules

These rules apply to frontend application work. They are guidelines to adapt to the feature and existing UI, not a mandate to rewrite existing pages.

## Design

- Give each page one clear purpose and primary action.
- Prefer progressive disclosure: essential job and application information first, secondary detail behind a drawer, panel, or focused section.
- Convert backend values into user-facing labels.
- Do not add raw database IDs, foreign keys, debug metadata, or unformatted timestamps to new user-facing UI.
- Keep forms readable and preserve responsive hierarchy.
- Reuse existing Tailwind styles and components before adding a new visual pattern.

## Page patterns

Choose the closest pattern before implementing a new or substantially changed page:

- List: scanable collection, filters, and an explicit empty state.
- Form: focused input flow with required fields first.
- Detail: summary first, then grouped secondary information.
- Canvas/workspace: dominant work area with compact secondary controls.
- Empty state: no-data explanation plus a clear next action.
- Modal/focused interaction: small secondary action, not primary navigation.

## Scaffold guidance

The template names `PageLayout`, `PageHeader`, `Section`, `FormContainer`, and `Stack` as preferred layout primitives. They do not yet exist in this repository. When they provide value for new work, place them under `frontend/src/components/ui/` and introduce them incrementally.
