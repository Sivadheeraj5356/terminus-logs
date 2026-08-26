# Risk bulletin schema

## Top-level fields

`emitted_at`, `cutoff`, `contam_summary`, `contam_rows`, `session_scorecard`, `coverage`, `attestation`.

## contam_summary

Keys: `sessions_in_corpus`, `failures_analyzed`, `contaminated_failures`, `sessions_flagged`.

## contam_rows

Sort by `(session_id, turn_id, contam_id)`.

Fields: `contam_id`, `session_id`, `turn_id`, `failure_id`, `attribution_primary`, `severity_score`, `evidence`.

### evidence

Exactly eight tokens, then sort lexicographically:

| Prefix | Value |
|--------|-------|
| `session:` | session_id |
| `turn:` | turn_id |
| `failure:` | failure_id |
| `cause:` | attribution_primary |
| `retrieval:` | triggering query_key or `none` |
| `tool:` | triggering tool_id or `none` |
| `instruction:` | later conflicting version_id or `none` |
| `status:` | `flagged` |

## session_scorecard

One row per session with eligible assistant turns. Sort by `session_id`.

Fields: `session_id`, `eligible_assistant_turns`, `contaminated_failures`, `severity_score`, `needs_review`.

`needs_review` is true when `severity_score < min_severity_score` from policy.

## attestation

Exactly:

```
{"attest_digest": "<sha256>"}
```

Digest is SHA-256 over compact JSON with keys `cutoff`, `contaminated_failures`, `emitted_at` sorted lexicographically.

## coverage

`coverage_total` = sessions in corpus after last-wins. `coverage_evaluated` = sessions with at least one eligible turn.
