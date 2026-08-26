# State layout

A lab root contains immutable inputs and mutable state:

```text
fixtures/users.db
fixtures/tokens.db
pam.d/*.conf
state/journal.log
state/faillock.db
state/tokens.db
state/sessions.db
state/audit.log
checkpoints/<label>/journal.log
checkpoints/<label>/meta.txt
checkpoints/<label>/projections/*
```

Database files use pipe-separated records and reject malformed rows. User and identifier fields must not contain a pipe or newline. `authctl bootstrap` creates projections from fixtures. `authctl rebuild` discards only the projections, reinitializes them from fixtures, and replays every journal event in sequence.

`authctl checkpoint --label NAME` captures the current journal and projection files. `authctl restore --label NAME` returns the lab to that saved point and must be safe to run twice in a row.

The normalized `authctl snapshot` output is stable and sorted so live and rebuilt state can be compared byte-for-byte.

Disposable labs are created under a caller-chosen root with `authctl bootstrap`.
