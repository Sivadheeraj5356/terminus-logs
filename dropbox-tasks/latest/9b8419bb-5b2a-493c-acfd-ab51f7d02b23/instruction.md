# Mission readiness governance desk

Fix the source under /app/environment so the Mission Readiness Review Board command regenerates a consistent determination from a supplied record directory. Build and run /app/bin/boardctl review with a record directory, policy JSON, output directory, and persistent state file; an optional clear-state switch empties prior state before the review. The verifier uses /app/environment/data/policy_standard.json, bundled orbital records, and generated records that change evidence order, policy floors, shared state, repeated reviews of the same case, overdue commitments, and invalid authority declarations.

Go and Rust toolchains are installed in the image. After editing sources under /app/environment, rebuild /app/bin/boardctl with go build from /app/environment targeting cmd/boardctl, and rebuild the index helper with `cargo build --release --locked --manifest-path /app/environment/z4/Cargo.toml` (install the release binary as /app/bin/ixcore). Confirm both builds succeed before relying on regenerated artifacts; the verifier also rebuilds from your sources.

## Outputs

Write /app/output/determination.json, /app/output/evidence_matrix.csv, /app/output/board_memo.txt, /app/output/board_state.json, and /app/output/review_journal.jsonl, and print one summary line of the form case=<id> decision=<decision> resilience_index=<n>.

The board accepts engineering technical certification as an official fact and must not recalculate or negate it. Governance covers operational preparedness, emergency authority, safety, crew support, independent oversight, dissent handling, and organizational commitments.

## Authority gate

Publication requires emergency authority status exactly delegated with a non-empty decision document. Any other authority status, or a missing emergency authority declaration, must exit nonzero without writing determination, matrix, memo, output state copy, or journal lines for that attempt. Rejection stderr must identify both emergency and authority.

## Evidence merging

Duplicate evidence ids must merge independent of input order. Stronger status severity wins among ready, watch, gap, and blocked. When severity ties, axis, weight, and note come from the independent copy when exactly one copy carries independent provenance; otherwise from the copy whose note is lexicographically smaller; if notes also tie, from the copy with the smaller weight. Independent provenance wins when present on either copy. Stronger dissent wins among none, minor, major, and critical. A concern stays unresolved if any duplicate copy is unresolved.

Axis contribution per merged row: ready adds weight, watch adds zero, gap subtracts weight, blocked subtracts twice the weight. Unresolved critical and major dissent counts include every unresolved merged row at that dissent level; source does not exempt a row.

## Decision logic

Decision tokens are AUTHORIZE, CONDITIONAL_AUTHORIZE, and POSTPONE. Prefer POSTPONE for any axis score below its policy floor, for positive unresolved critical dissent while critical-dissent stopping is enabled, or for authority other than delegated. Prefer CONDITIONAL_AUTHORIZE for positive unresolved major dissent while major-dissent conditioning is enabled, for any remaining open commitment, or for any open commitment past due (due_day plus commitment_due_margin_days is less than mission_days). Otherwise prefer AUTHORIZE.

## Commitments and state

Commitment reconcile is case-specific. The case prior open and closed sets combine with record commitments by id. An id that appears closed in prior state or in the record remains closed in the result. State is keyed by case id, advances run_count on each successful review, clears only under the clear-state switch, and must not leak commitments across cases that share one state file.

## Resilience index

Resilience uses the Rust index helper installed at /app/bin/ixcore (crate manifest /app/environment/z4/Cargo.toml). Feed sorted axis lines plus critical, major, delegated, and stagnation fields. Index equals clamp(0, 100, 50 + sum(axis)*4 - critical*18 - major*7 - (25 if not delegated else 0) - stagnation_penalty). stagnation_penalty follows the follow-up rule documented beside the index helper in /app/environment/board_contract.md. Labels: strong from 82 upward, guarded from 62 upward, otherwise fragile. The memo must report the resilience index with its label in the form Resilience index: N (label).

## Journal and cross-artifact consistency

Each successful review appends one JSON line to /app/output/review_journal.jsonl carrying case_id, decision, resilience_index, run_count, open_commitment_ids, stagnation_penalty, and overdue_open. The latest journal line for a case must agree with /app/output/board_state.json on run_count, last decision, and open commitment ids, and with /app/output/determination.json on resilience_index, stagnation_penalty, and overdue_open. /app/output/board_state.json must record the case id, run_count, last decision, open commitments, and closed commitments for each case. Determination, CSV TOTAL, memo, state, journal, and stdout must agree on case id, decision, unresolved dissent counts, open and closed commitment ids, axis scores, resilience index, and stagnation penalty.

## Artifact formats

The CSV at /app/output/evidence_matrix.csv lists merged evidence rows plus a final TOTAL row with decision and resilience index. /app/output/determination.json includes accepted certification text, raw emergency authority status token, per-axis scores, dissent counts, commitment id lists, resilience index, stagnation penalty, and boolean overdue_open. The memo at /app/output/board_memo.txt must state that technical certification was accepted as record, name the authority status, report the resilience index with its label, and include a Rejected alternatives line listing the two unused recommendations in preference order AUTHORIZE, then CONDITIONAL_AUTHORIZE, then POSTPONE, using the compact form Rejected alternatives: A,B. Every memo line ends with a period.

Static hand-written outputs, test edits, or wrapper-only changes are insufficient; the verifier rebuilds the tools and regenerates artifacts for mutated records.
