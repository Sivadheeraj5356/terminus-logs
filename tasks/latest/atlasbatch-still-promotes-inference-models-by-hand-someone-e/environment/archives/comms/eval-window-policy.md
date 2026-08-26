# Evaluation freshness policy (ratified 2026-03-20)

Promotion candidates must be evaluated within the active evaluation window relative to the clock in `/app/config/eval-clock.toml`.

## Window length

The holdout evaluation recorded in `candidates.eval_completed_at` must fall on or after the date that is **14 calendar days before** `as_of_date`. Evaluations completed earlier are stale and must not promote.

## Example

When `as_of_date = "2026-04-15"`, the earliest acceptable `eval_completed_at` is `2026-04-01`.

## Supersedes

This policy replaces the 30-day window described in `/app/archives/engineering/promotion-gates-legacy.md`.
