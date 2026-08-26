# Audit fields and durable state

Fixture packs under `fixtures/qv/` each contain `arm`, `phase` (`normal`, `cut`, `recover`,
`partial`, or `stale`), `row_cap`, `group_cap`, and a `cells` array. Every cell carries `id`,
`kind` (`host` or `path`), `match`, `target`, and `want` (`route` or `deny`).

## `/app/output/haproxy_route_audit.json`

- `arm` — active arm name
- `rule_rows` — emitted rows after fold and tally. Each row is a flat object with keys `Kind`,
  `Match` (JSON array of matcher strings, sorted), `Target`, `Want`, `Mode`, `Group`, `Key`,
  `Seq` (the session generation at fold time — it varies run to run and stays out of the
  seals). Never-mode rows precede always-mode rows. Length ≤ `expected_row_cap`; under
  ceiling-aware packing the always-row count equals the number of distinct (kind, target)
  pairs among route cells.
- `route_count` — length of `rule_rows`
- `group_count` — length of `group_keys`
- `cell_outcomes` — one `{id, outcome, target, group}` object per fixture cell. Route cells
  read `hit` with the published target and the covering row's group; deny cells read `deny`
  with empty target and empty group.
- `group_keys` — sorted distinct group strings from always-mode rows; length ≤
  `expected_group_cap`; one key per (kind, target) pair.
- `hop_records` — one `{id, cover, group}` object per **routed cell** (outcome `hit`), sorted
  by id, where `id` is the cell id (never the matcher), `cover` is `always`, and `group`
  equals that cell's outcome group and appears in `group_keys`.
- `pane_digest` — JSON string; sha256 hex of exactly 64 hexadecimal characters over the
  canonical arm parts (arm name, sorted cell outcome lines, group lines, sorted row lines).
  The seal excludes session counters, so regenerating an unchanged arm reproduces the digest.
- `twin_digest` — second seal pass of the same formula; must equal `pane_digest` within a
  run, and held_out regenerations across consecutive runs keep both identical.
- `expected_row_cap` / `expected_group_cap` — published ceilings copied from the fixture
- `session_floor` / `session_gen` — durable counters from `state/session.registry` after the arm
- `interrupt` — true only for cut-phase arms
- `run_stamp` — sha256 hex over the line `<arm>:<pane_digest>:<session_floor>:<session_gen>`
  plus a trailing newline
- `generation` — the generation number committed by this arm (0 for cut-phase arms)
- `manifest_seal` — the committed generation's seal (empty for cut-phase arms)
- `ledger_head` — hash of the last ledger entry at emit time
- `plan_token` — the token the commit was admitted under
- `status` — `ok` for committed arms, `interrupted` for cut-phase arms

Cut-phase arms (`phase=cut`) publish `interrupt=true`, `status=interrupted`, and **empty**
`rule_rows`, `cell_outcomes`, `group_keys`, and `hop_records` (`route_count` and
`group_count` both 0). The prepared rows exist only in the cut journal — they are never
sealed inventory, and a cut arm commits no generation and appends no ledger entry.
`pane_digest`, `twin_digest`, and `run_stamp` are still sealed over the prepared plan.

## Public commands

One binary drives everything:

```
lb_drive --arm <name> --out <path>        # plan and commit in one pass
lb_drive plan --arm <name> --out <path>   # write a plan; token on stdout
lb_drive commit --plan <path> --cas <token> --out <path>
lb_drive status                           # session counters and pointers, JSON on stdout
lb_drive verify                           # chain/pointer/anchor audit, JSON on stdout
lb_drive replay                           # rebuild registry and current from the ledger
lb_drive recover                          # quarantine corrupt generations; prints "<gen> <seal>"
```

Plan documents land wherever `--out` points; the conventional spot is
`/app/var/qxhub/plans/<arm>_plan.json` (for example `dense_plan.json` or
`held_out_plan.json`). A plan token is the sha256 hex of `plan|<arm>|<gen>|<pane_digest>`
where `<gen>` is the session generation the plan was built at. Committing a plan whose
generation no longer equals the live `active_gen` is a **stale commit**: it must fail with a
non-zero exit and leave the ledger, generations, `state/current`, and the registry untouched.

Commits are idempotent. The transaction id is the first 24 hex characters of the sha256 of
`tx|<arm>|<gen>|<pane_digest>`; committed ids are recorded under `state/txns/`. Re-committing
a recorded transaction re-emits the audit and exits 0 without appending a ledger entry,
writing a generation, or advancing the session.

## Durable state

- `state/session.registry` — JSON with `active_gen`, `floor`, `anchor`, `epoch`, `last_arm`.
  `anchor` is the lowercase hex of `active_gen*13 + floor*5 + epoch`, resealed after every arm.
- `state/ledger.jsonl` — append-only commit ledger, one JSON object per line with fields
  `prev`, `gen`, `floor`, `epoch`, `arm`, `seal`, `tx`, `hash`. `hash` is the sha256 hex of
  `<prev>|<gen>|<arm>|<seal>|<tx>` (recomputable with the stock `sha256sum` tool); `prev` is
  the previous entry's `hash` (`0` for the first entry). A torn final line — an interrupted writer's partial JSON — must be truncated away
  before a recover-phase arm replays or appends; every surviving line stays parseable and the
  chain recomputes end to end.
- `state/generations/<gen>/` — one immutable directory per committed generation holding
  `manifest.json` and `MSEAL`. `MSEAL` is the sha256 hex over the exact `manifest.json`
  bytes. The manifest carries `generation`, `arm`, `pane`, sorted `groups`, and `rows`
  (each `{kind, mode, target, match, group}`). The generation number equals the post-advance
  `active_gen` of its commit.
- `state/current` — the current generation number, one line.
- `state/txns/` — recorded transaction ids, one empty marker file per commit.
- `state/quarantine/` — where `recover` moves generation directories whose `manifest.json`
  bytes no longer match their `MSEAL`. `recover` walks generations newest to oldest,
  quarantines every corrupt one, resets `state/current` to the newest intact generation, and
  prints that generation number and its seal.
- `state/journal/cut.jnl` (absolute path `/app/environment/state/journal/cut.jnl`) —
  cut-phase arms record their journal under that fixed name (never named after the arm). The entry is JSON with `arm`, `pending` (the prepared row count),
  and `hint`. Recover-phase arms consume every `.jnl` file and remove
  `/app/var/qxhub/lane.shadow` before folding.
- `/app/var/qxhub/lane.shadow` — scratch hint surface; never a fold input (see rx_board.md).

`replay` rebuilds a lost `state/session.registry` and `state/current` from the last ledger
entry: `active_gen`, `floor`, and `epoch` are restored from that entry's recorded values, the
anchor is resealed from the formula, `last_arm` is the entry's arm, and `state/current` is
rewritten to the entry's generation. Replay never invents decisions — arms that append no
ledger entries (cut arms) are not reconstructed.

## Session advance rules

Applied once per committed arm, then the anchor is resealed:

- `normal` and `stale` phases: `active_gen` +1, `floor` +1, `epoch` +1.
- `cut` phase: `active_gen` +1; `floor` and `epoch` unchanged — the cut opens a floor gap.
- `partial` phase: `active_gen` +1, `epoch` +1; `floor` unchanged.
- `recover` phase: `active_gen` +1, `epoch` +1; `floor` catches up to `active_gen - 1`.
- `floor` stays strictly below `active_gen` at all times; audits report the post-arm values.
