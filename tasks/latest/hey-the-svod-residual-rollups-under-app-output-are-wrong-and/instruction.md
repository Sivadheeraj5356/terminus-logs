Hey — the SVOD residual rollups under `/app/output/` are wrong and incomplete after we merged the new usage shards.

Build the Go processor under `/app` so `go run ./cmd/residual` reads every JSONL shard under `/app/data/usage`, the catalog CSVs under `/app/data/`, and config under `/app/config/`, leaves all inputs byte-identical, and writes `/app/output/residual_daily.csv`, `/app/output/residual_weekly.csv`, and `/app/output/escrow_ledger.jsonl`. Use only the Go standard library (`GOPROXY=off`). Do not hardcode rollup results for the bundled feeds alone. The stub compiles but emits incorrect partial output — replace it with the full end-to-end pipeline.

Outputs must satisfy the contracts in `/app/docs/usage_feed_contract.md`, `/app/docs/catalog_reference.md`, `/app/docs/rate_and_recoupment.md`, `/app/docs/allocation_contract.md`, and `/app/docs/output_contract.md` — including JSONL dedup precedence, integer micro-cent accrual with truncation, territory-local `dayLocal`, weekly rollup invariants, recoupment waterfall, participant remainder ordering, and the escrow HMAC footer format.

Acceptance checklist:

1. Load manifest-listed usage shards first, then unlisted `*.jsonl` shards by lexicographic basename.
2. Keep source-line metadata as the 1-based count of non-blank data lines; blank lines do not increment it.
3. Skip malformed rows after emitting the exact stderr audit line required by the usage feed contract.
4. Resolve aliases case-insensitively and ignore unknown aliases, inactive works, unknown territories, and unsupported media.
5. Deduplicate with the full precedence chain: revision, captured UTC instant, manifest position, then source line.
6. Compute `dayLocal` in the territory IANA zone, including both spring-forward gaps and fall-back ambiguous hours.
7. Accrue with integer arithmetic and truncation; do not use floating point for money.
8. Derive weekly rows from daily rows and preserve all documented sort orders.
9. Apply recoupment only in escrow, split remainders by ascending `catalogIndex`, and omit zero-amount participants.
10. Emit only the latest escrow `periodMonth`, with compact JSON key order and a footer HMAC keyed by `ESCROW_AUDIT_SECRET`.
11. Preserve every input file byte-for-byte and make reruns overwrite stale outputs.

Hand-written JSON or CSV will not pass verification. The shape helper under `/app/internal/validate/` checks headers and JSON parseability only; it does not verify monetary totals, ordering, HMACs, stderr audits, or cross-artifact consistency. Passing that helper is not evidence that the task is solved.
