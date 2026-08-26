# Contamination attribution

## Eligible turns

Include conversation turns with `completed_at <= cutoff`. Sort per session by `(completed_at, turn_id)`.

## Contam rows

Emit one row for each model-output failure whose assistant `turn_id` is eligible. Identifier:

```
contam_{session_id}_{turn_id}
```

## Cause precedence

Pick the first applicable cause in this order:

| Cause | Rule |
|-------|------|
| `instruction_conflict` | At least two system-instruction versions with `effective_from <= failure turn completed_at`, and a later version lists an earlier `version_id` in `conflicts_with` |
| `stale_retrieval` | A retrieval with `retrieved_at <= failure turn completed_at` (and `<= cutoff`) shares `query_key` with a strictly later retrieval (`retrieved_at` greater, still `<= cutoff`) that has a different `content_hash`. The later retrieval may occur after the failure turn. Equal timestamps are not "later" and do not qualify. |
| `tool_artifact_bleed` | A tool execution with `executed_at <= failure turn completed_at` exists on an earlier or equal turn in the same session |
| `repeated_fact_injection` | Count of eligible retrievals in the session before/at failure with the same `content_hash` is `>= repeat_fact_threshold` from policy |
| `residual_contam` | Failure present with no higher cause |

## Severity

Per session:

```
severity_score = round(1 - contaminated_failures / eligible_assistant_turns, score_precision)
```

`eligible_assistant_turns` counts assistant-role turns with `completed_at <= cutoff`. Sessions with zero eligible assistant turns omit a scorecard row. Whole values emit as JSON integers.

## Mutation witness and replay

Each sealed bulletin carries a mutation witness digest over the freeze clocks. Emit must replay the sealed freeze payload without recomputing rows. A checksum mismatch on mutation_attest or pin_digest rejects the emission. Idempotent re-score with identical clocks must not change sealed witness bytes.
