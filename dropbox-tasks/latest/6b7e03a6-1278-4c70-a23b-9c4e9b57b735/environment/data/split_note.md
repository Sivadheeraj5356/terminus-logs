# Split design

The `domain` column is derived from the session's calendar month. Off-
season months are the `source` domain; the peak shopping-season months
are the `target` domain (the deployment regime). The raw month is not
included as a feature.

- source sessions: all labeled
- target sessions: only a labeled pilot is provided, the rest are
  unscored (blank `target`)

Counts and per-column summaries are in the shipped summary files; derive
any rates you need from the data itself.
