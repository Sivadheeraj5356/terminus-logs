# Formal properties for the build proof workshop

## Build and replay

Rebuild the locked driver after source edits.

```bash
make -C /app/environment bp_run
```

Compile TypeScript sources (typecheck only).

```bash
/app/environment/node_modules/.bin/tsc --noEmit -p /app/environment
```

Run the full certification pipeline.

```bash
bash /app/environment/scripts/bp_run --phase all --emit /app/output/cert_report.json
```

Status probe (does not replace a full emit).

```bash
bash /app/environment/scripts/bp_run --gauge
```

Profile drill `profile_a` rewrites the durable ledger and must finish with a fresh trace whose `ledger_mtime` field increases.

Operator argv patterns are listed in `/app/environment/docs/operator_cmds.txt`.

## Output artifacts

- `/app/output/cert_report.json` with `schema_version` `row_v4` per `/app/environment/schemas/row_v4.schema.json`
- `/app/output/run_traces/last.json` phase log with `drill`, `jobs`, and `ledger_mtime` fields
- `/app/output/witness_meta/*.bin` byte sidecars for non-echo report rows only. Each coherent base row (any `arm_id` that does not end in `_echo`) has exactly one sidecar; echo rows must not emit sidecars. The sidecar count equals the number of coherent non-echo rows. Each sidecar filename is `${row_seed}.bin` where `row_seed` is the row's decimal seed integer written without leading zeros (the stem must parse as a base-ten integer). Each sidecar must be exactly eight bytes (length 8). Bytes 0 through 3 are a big-endian unsigned thirty-two-bit integer whose lower sixteen bits carry the proof contribution folded into `facet_material`. Bytes 4 through 7 encode the row seed as an unsigned thirty-two-bit big-endian integer. Sidecars shorter than eight bytes are invalid.
- `/app/environment/state/k3_ledger.tsv` durable build ledger (rewritten each emit). Each row records `proof_hex`, a lowercase hex encoding of the proof contribution only. Parsed as an integer, `proof_hex` must equal the lower sixteen bits of that arm's `facet_material` (`int(facet_material, 16) & 0xFFFF`).

## Row fields

Each row carries `arm_id`, `facet_material`, `expand_rc`, `merge_rc`, `proof_rc`, and `lag`.

The `facet_material` field spans sixteen lowercase hex characters (length 16). The summary `cert_digest` field also spans sixteen lowercase hex characters (length 16).

Coherent terminal rows keep `lag` at zero. The `expand_rc` field reports optional edge expansion completeness when set to `1`. The `merge_rc` field reports parallel merge injection when set to `1`. The `proof_rc` field reports witness_meta byte agreement when set to `1`.

## Echo pairs

For each primary arm id in `/app/environment/docs/primary_flags.txt`, the echo variant appends `_echo` to the same stem. Coherent runs agree on `facet_material` and the three `*_rc` fields between each pair. Echo rows mirror their base partner but do not get separate witness sidecars.

## Summary

`summary.rows_total` equals the `rows` array length. `summary.span_band` is the maximum absolute `lag` magnitude across rows. `summary.sync_label` is `steady` only when every row is coherent. `summary.cert_digest` is the fnv1a-64 digest over comma-joined sorted `facet_material` values (see reduction comment in `/app/environment/pilot/entry.ts`).

## Generalization

Held-out flag permutation scenarios live in `/app/environment/data/extra_flags.toml`. Each `[[hold]]` block carries a `slug` label and parallel `jobs` count. A correct repair generalizes to every scenario row under varying parallel job counts.

## Phases

The driver runs property-gated expansion, merge injection, topological proof emit, and cross-format row materialization in that order. Terminal `*_rc` values must be derived on the wired mux path rather than reimplemented in orchestration wrappers alone.

Mux helpers own phase outcomes. Orchestration wrappers call those helpers and assign row counters from helper return codes only. Recomputing counters from local heuristics, defaulting counters to success when helpers fail, or clamping faults in the pipeline layer violates the contract. Helper faults must propagate into the matching row counter.

When the expansion gate is armed, `expand_rc` is `1` only if the bridge reports at least two manifest outputs. `merge_rc` reflects whether parallel edge injection succeeded for the row context (rows with `jobs` above one require a successful injection). The proof phase writes one eight-byte witness sidecar per non-echo row under `/app/output/witness_meta/`. Materialization re-reads those sidecars and sets `proof_rc` by cross-checking folded facet material against on-disk bytes; earlier phase counters are not authoritative for `proof_rc`.

The `--gauge` subcommand emits an interim status view whose `label` may read `pending` before terminal coherence; it is not sufficient on its own.

## Recovery

After a destructive clean step, rerun the full operator argv sequence from `operator_cmds.txt` idempotently to reach the same terminal `cert_digest`.
