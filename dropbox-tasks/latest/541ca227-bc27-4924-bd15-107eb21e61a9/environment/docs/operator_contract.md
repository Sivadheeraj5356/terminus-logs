# Operator contract

## Fingerprint

Sort rows by `(prefix, via)` ascending. Serialize to JSON as an array of objects
`{"p": "<prefix>", "v": "<via>", "c": <class uint8>}`. The fingerprint is the
lowercase hex sha256 digest of that UTF-8 JSON (no whitespace outside strings).

## CLI and fixtures

Commands: `linkctl boot`, `linkctl reconfigure`, and `linkctl recover` accept
`--profile`, `--root`, and `--out` (recover omits profile requirement but may
take `--profile` for probe layout). Bundled profile labels include `alpha`,
`beta`, and `gamma`. Topology fixture objects carry `manager_rows`, `catch_rows`,
and `churn_seq`. Grant-feed JSON lines carry `kind` (`G` grant, `W` withdraw),
`prefix`, and `seq`.

## Feed replay horizons

Cold boot replays every grant/withdraw event in `/app/var/grant_feed.jsonl` with
no sequence ceiling. Rebuild `ActivePref`, `Epoch`, and `Fence` from scratch.

On grant (`G`): `Epoch++`, `Fence++`, and `ActivePref[prefix]=true`.

On withdraw (`W`): `Epoch++`, `Fence++`, and the prefix is removed from
`ActivePref` (it must not remain listed as inactive).

In-place profile reload onto profile P: reset the feed state and replay events
with `seq <= P.churn_seq` from scratch. Do not re-apply reload events on top of
the cold-boot full feed replay.

## Cold FIB composition

After cold boot for profile P, effective rows are:

- shim-injected static rows promoted from quarantine (class 2),
- catchment defaults from P (class 3),
- manager-origin dynamic rows from P whose prefixes are active after full feed
  replay (class 1).

## Incremental reload merge

Starting from a prior effective table (typically cold-booted on an earlier
profile), merge onto profile P:

1. Keep every prior class-2 (shim-injected) row.
2. Keep prior class-3 (catchment) rows whose keys are absent from P's
   `catch_rows`; then add P's catchment rows.
3. Rebuild class-1 (dynamic) rows from P's `manager_rows` using the feed replayed
   only through P's `churn_seq`.
4. Deduplicate by `key` (last write for a key wins).

## Quarantine and fence admission

Shim foreign rows enter a quarantine ledger. When a fixture row omits
`admit_fence`, `AdmitFence` equals the feed `Fence` after replay at admission.
When `admit_fence` is present on the fixture row, that value is the admission
threshold. Rows promote into the registry as class 2 only when current
`Fence >= AdmitFence`. Rows whose threshold is above the reachable fence (for
example `f-shim-hold` with `admit_fence` 99) must remain quarantined and must
not appear in `effective_fib.json`. On reconfigure, re-load missing foreign rows
into quarantine and promote with the current `Fence`.

## Transaction sealing

Planning writes `Planned[gen]`. Commit copies `Planned` into `Committed[gen]`
and clears the open planned generation. Published tables and status mirrors must
follow sealed committed generations, not open planned generations.

## Write-ahead log

Each plan appends a WAL frame with `sealed=false` and a row snapshot. Commit seals
that frame. `linkctl recover` rebuilds registry, tags, generation, and
transaction tip from the last **sealed** WAL frame only; unsealed frames are
ignored. If `snap.json` is corrupt or missing, recovery from the sealed WAL tip
still succeeds. Recovery is idempotent.

## effective_fib.json

Object with `rows` (array of `{key, prefix, via, class}`) and `fingerprint`
(must equal the formula above for `rows`).

## link_status.json

Object with `probes`: array of `{slot_id, carrier_up, mirror_gen}`. Probes may
read carrier-up while the row table is still catching up; `mirror_gen` must match
the last sealed committed generation when the published table has caught up.

## reconfigure_journal.jsonl

One JSON object per line: `phase` is `plan`, `commit`, or `recover`;
`gen_planned` and `gen_committed` are unsigned integers; `profile` names the
active profile label.

## Row classes

`class` 1 = dynamic rows tied to the grant feed, 2 = shim-injected static rows,
3 = catchment defaults from the profile fixture.

Persisted state under `/app/var/state/snap.json` includes feed `epoch`, `fence`,
`last_seq`, and `active_pref` (prefix to bool map reflecting grant/withdraw
replay), plus quarantine pending entries when present.
