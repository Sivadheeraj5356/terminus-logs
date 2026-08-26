# Feature and eval metric contract

wincontam is a machine-learning evaluation capability: it builds contamination-aware inference features from conversation timelines and scores deterministic eval metrics used as training-signal diagnostics.

## Feature batch fields

Each `contam_rows` entry is one inference-time feature row for a failed assistant turn:

| Field | Role |
|-------|------|
| `contam_id` | Stable feature key `contam_{session_id}_{turn_id}` |
| `attribution_primary` | Process-cause feature for the failure |
| `severity_score` | Session-level eval metric copied onto each row |
| `evidence` | Eight sorted tokens used as sparse feature tags |

## Eval metrics

`contam_summary` and `session_scorecard` are the primary eval metric surfaces:

- `contaminated_failures` / `failures_analyzed` count scored rows.
- `severity_score` is `round(1 - contaminated/eligible_assistant_turns, score_precision)`.
- `needs_review` is true when `severity_score < min_severity_score`.
- `attestation.attest_digest` binds the metric clocks and contaminated failure count.

Identical corpus, `--cutoff`, and `--emitted-at` must yield byte-identical metric bulletins.
