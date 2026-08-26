# Alias and lag notes

Some sample streams still emit legacy aliases. Remap packs may chain through
intermediate ids, and the active mapping can change by `active_from_ms`.
Feature packs may also contain poison revisions keyed by an alias string
itself. Those must not win after full as-of resolution.

Fold lag shifts only the valid_from horizon. Output `asof_ms` stays on the
original sample timestamp.
