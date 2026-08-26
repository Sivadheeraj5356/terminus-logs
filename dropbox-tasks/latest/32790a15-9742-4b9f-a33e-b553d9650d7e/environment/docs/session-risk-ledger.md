# Session risk ledger

`session_risk_ledger.json`:

| Field | Meaning |
|-------|---------|
| `corpus_stamp` | Must match freeze |
| `cutoff` / `emitted_at` | Must match evaluation clocks |
| `receipt_kind` | Always `severity_scorecard` |
| `sessions_flagged` | Count of scorecard rows with `needs_review` true |
| `receipt_digest` | SHA-256 over compact sorted JSON of `{cutoff, corpus_stamp, emitted_at, receipt_kind, sessions_flagged}` |
